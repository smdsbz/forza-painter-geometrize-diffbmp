import argparse
import json
import os
import sys
from pathlib import Path

# Fix Unicode emoji prints on Windows GBK terminals
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def _find_cairo_dll():
    """Search common MSYS2 install paths for libcairo-2.dll."""
    _candidates = [
        r"C:\msys64\mingw64\bin",
        r"C:\msys64\ucrt64\bin",
        r"C:\msys64\clang64\bin",
    ]
    import ctypes
    for _d in _candidates:
        _dll = os.path.join(_d, "libcairo-2.dll")
        if os.path.isfile(_dll):
            os.add_dll_directory(_d)
            ctypes.CDLL(_dll)
            return
    raise RuntimeError(
        "\u672a\u627e\u5230 Cairo DLL\u3002\u8bf7\u5b89\u88c5 MSYS2 \u5e76\u6267\u884c:\n"
        "  winget install MSYS2.MSYS2\n"
        "  pacman -S mingw-w64-x86_64-cairo"
    )

if sys.platform == "win32":
    _find_cairo_dll()

import numpy as np
import torch
from PIL import Image

from pydiffbmp.core.preprocessing import Preprocessor
from pydiffbmp.core.renderer.simple_tile_renderer import SimpleTileRenderer
import pydiffbmp.core.renderer.simple_tile_renderer as _simple_tile_renderer
from pydiffbmp.core.initializer.svgsplat_initializater import StructureAwareInitializer


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # src/forza_painter_geometrize_diffbmp/fit_image.py -> root


def load_config(config_path: Path, image_path: str) -> dict:
    with open(config_path) as f:
        config = json.load(f)
    pp = config.setdefault("preprocessing", {})
    pp["img_path"] = image_path
    pp.setdefault("do_equalize", False)
    pp.setdefault("do_local_contrast", False)
    pp.setdefault("do_tone_curve", False)
    pp.setdefault("bg_threshold", 250)
    pp.setdefault("vertical_paddings", [0, 0])
    pp.setdefault("local_contrast", {"radius": 2.0, "amount": 3.0})
    pp.setdefault("tone_params", {})
    pp.setdefault("exist_bg", True)
    pp.setdefault("trim", False)
    pp.setdefault("FM_halftone", False)

    opt = config.setdefault("optimization", {})
    opt.setdefault("learning_rate", {})
    lr = opt["learning_rate"]
    lr.setdefault("gain_x", 10.0)
    lr.setdefault("gain_y", 10.0)
    lr.setdefault("gain_r", 10.0)
    lr.setdefault("gain_v", 1.5)
    lr.setdefault("gain_theta", 1.0)
    lr.setdefault("gain_c", 1.0)
    opt.setdefault("bg_color", "white")

    return config


def resolve_primitive_paths(config: dict) -> list[str]:
    files = config.get("primitive", {}).get("primitive_file", [])
    if isinstance(files, str):
        files = [files]
    resolved = []
    for f in files:
        p = Path(f)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        resolved.append(str(p))
    return resolved


def load_primitive_bitmaps(paths: list[str], output_width: int, device: torch.device):
    """Load PNG primitives directly, bypassing cairosvg dependency."""
    bitmaps = []
    colors = []
    for path in paths:
        img = Image.open(path).convert("RGBA")
        img = img.resize((output_width, output_width), Image.LANCZOS)
        arr = np.array(img, dtype=np.float32) / 255.0  # [H, W, 4]
        alpha = arr[:, :, 3]                            # [H, W] float32
        rgb = arr[:, :, :3]                             # [H, W, 3] float32
        bitmaps.append(torch.tensor(alpha, device=device))
        colors.append(torch.tensor(rgb, device=device))
    S = torch.stack(bitmaps)              # [p, H, W]
    cmaps = torch.stack(colors)           # [p, H, W, 3]
    return S, cmaps


def fit_image(config: dict, render_process: bool = False) -> str:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}", file=sys.stderr)

    # ── 1. load target image ──────────────────────────────────────────
    pp_cfg = config["preprocessing"]
    preprocessor = Preprocessor(final_width=pp_cfg.get("final_width", 256))
    target_np = preprocessor.load_image_8bit_color(pp_cfg)
    H, W = preprocessor.final_height, preprocessor.final_width
    I_target = torch.tensor(target_np.astype(np.float32) / 255.0, device=device)
    print(f"target: {W}x{H}", file=sys.stderr)

    # ── 2. load primitives ────────────────────────────────────────────
    prim_cfg = config["primitive"]
    primitive_paths = resolve_primitive_paths(config)
    output_width = prim_cfg.get("output_width", 256)
    S, primitive_colors = load_primitive_bitmaps(primitive_paths, output_width, device)
    p = S.size(0)
    print(f"primitives: {p} templates, size {S.shape[1]}x{S.shape[2]}", file=sys.stderr)

    # ── 3. create renderer ────────────────────────────────────────────
    opt_cfg = config["optimization"]
    init_cfg = config["initialization"]
    post_cfg = config.get("postprocessing", {})

    image_name = Path(pp_cfg["img_path"]).stem
    if render_process:
        out_dir = Path(post_cfg.get("output_folder", "./outputs/"))
        if not out_dir.is_absolute():
            out_dir = PROJECT_ROOT / out_dir
        process_dir = out_dir / f"{image_name}_process"
        process_dir.mkdir(parents=True, exist_ok=True)
        Image.fromarray(target_np).save(str(process_dir / "target.png"))
        renderer_out = str(process_dir)
    else:
        out_dir = Path(post_cfg.get("output_folder", "./outputs/"))
        if not out_dir.is_absolute():
            out_dir = PROJECT_ROOT / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        renderer_out = str(out_dir)

    renderer = SimpleTileRenderer(
        canvas_size=(H, W),
        S=S,
        alpha_upper_bound=opt_cfg.get("alpha_upper_bound", 1.0),
        device=device,
        tile_size=opt_cfg.get("tile_size", 32),
        sigma=0.0,
        c_blend=opt_cfg.get("c_blend", 0.0),
        primitive_colors=primitive_colors,
        output_path=renderer_out,
        max_prims_per_pixel=init_cfg.get("max_prims_per_pixel"),
    )

    # ── 4. initialize ─────────────────────────────────────────────────
    initializer = StructureAwareInitializer(init_cfg)
    x, y, r, v, theta, c = renderer.initialize_parameters(
        initializer=initializer,
        target_image=I_target,
    )
    print(f"initialized: {len(x)} primitives", file=sys.stderr)

    # ── 5. optimize ───────────────────────────────────────────────────
    if render_process:
        _simple_tile_renderer.DEBUG_MODE_SAVE = True
    x, y, r, v, theta, c = renderer.optimize_parameters(
        x, y, r, v, theta, c,
        target_image=I_target,
        opt_conf=opt_cfg,
        initializer=initializer,
    )

    # ── 6. render final ───────────────────────────────────────────────
    bg_color = opt_cfg.get("bg_color", "white")
    with torch.no_grad():
        final_bg = renderer._get_background_for_render(bg_color, export=True)
        rendered = renderer.render_from_params(
            x, y, r, theta, v, c,
            I_bg=final_bg,
            sigma=0.0,
            is_final=True,
        )
    if isinstance(rendered, tuple):
        rendered = rendered[0]

    rendered_np = rendered.detach().cpu().numpy()
    rendered_np = (rendered_np * 255).clip(0, 255).astype(np.uint8)

    if render_process:
        out_file = str(process_dir / "final.png")
    else:
        out_file = str(out_dir / f"{image_name}.png")
    Image.fromarray(rendered_np).save(out_file)

    # ── 7. postprocessing ──────────────────────────────────────────────
    if post_cfg.get("compute_psnr"):
        import math
        mse = np.mean((target_np.astype(np.float32) - rendered_np.astype(np.float32)) ** 2)
        if mse > 0:
            psnr = 20 * math.log10(255.0 / math.sqrt(mse))
            print(f"PSNR: {psnr:.2f} dB", file=sys.stderr)
        else:
            print("PSNR: ∞ dB", file=sys.stderr)

    print(f"saved: {out_file}", file=sys.stderr)
    return out_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit an image to geometric primitives with diffbmp")
    parser.add_argument("image", help="Path to the input image")
    parser.add_argument("-c", "--config", default="config/default.json",
                        help="Path to diffbmp config JSON (default: config/default.json)")
    parser.add_argument("--render-fit-process", action="store_true",
                        help="Save intermediate renders and target to <output>/<name>_process/")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    if not config_path.exists():
        print(f"config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path, os.path.abspath(args.image))
    out_file = fit_image(config, render_process=args.render_fit_process)
    print(out_file)


if __name__ == "__main__":
    main()
