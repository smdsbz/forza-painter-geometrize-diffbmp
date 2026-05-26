import sys


def _check_cuda():
    import torch
    import cuda_tile_rasterizer

    assert torch.cuda.is_available(), (
        "CUDA not available. Check torch installation: "
        "ensure torch is installed with CUDA support (e.g. cu126)."
    )
    assert cuda_tile_rasterizer.CUDA_AVAILABLE, (
        "CUDA tile rasterizer extension not compiled. "
        "Run: cd diffbmp\\cuda_tile_rasterizer && python setup.py build_ext --inplace"
    )
    print(f"diffbmp CUDA: OK | device={torch.cuda.get_device_name(0)}", file=sys.stderr)


def main() -> None:
    _check_cuda()
    print("Hello from forza-painter-geometrize-diffbmp!")
