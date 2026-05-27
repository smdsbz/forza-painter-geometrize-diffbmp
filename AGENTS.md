# AGENTS.md — forza-painter-geometrize-diffbmp

## 项目概述

Python 项目，封装 diffbmp（可微分位图渲染）将图像拟合为几何图元，用于 Forza painter 涂装导入。`diffbmp/` 目录是 **git 子模块**（smhongok/diffbmp）。`pydiffbmp` 以**路径依赖**方式从 `./diffbmp` 安装。

**禁止 hack 已安装的依赖包或 diffbmp 子模块。** diffbmp 不是本项目的维护范围。需要的修改通过项目代码（环境变量、PATH、配置）解决。

## 命令

```bash
uv sync                     # 安装依赖（torch cu126，阿里云镜像）
uv run generate-primitives  # 生成 28 个图元 PNG → primitives/
uv run fit-image <image>    # 用 config/default.json 拟合图像
uv run fit-image <image> -c my.json  # 自定义配置
```

没有配置 lint、typecheck 或测试命令。

## 关键版本约束

**torch 必须 `<2.7`。** torch 2.7+ 在 `compiled_autograd.h` 引入回归 bug（C2872: `std` 符号歧义），导致 MSVC 14.44+ 下无法编译 CUDA 扩展。如需重新编译 CUDA 扩展，请确认当前为 `torch==2.6.0+cu126`。

## CUDA 扩展（一次性编译）

`diffbmp/cuda_tile_rasterizer/cuda_tile_rasterizer/_C.cp311-win_amd64.pyd` 已为 SM 8.6（RTX 3060）编译。**不被 git 追踪**（子模块中的二进制文件）。重新编译步骤：

1. 打开 **Developer Command Prompt for VS 2022**（或用不含 `C:\msys64\usr\bin` 的终端——MSYS2 的 sh.exe 会把 MSVC 标志 `/showIncludes` 转成 `C:/msys64/showIncludes`）。
2. `cd diffbmp\cuda_tile_rasterizer`
3. **修改 `setup.py`**，在 `extra_compile_args` → `nvcc` 中添加你的 GPU 架构。当前为 SM 8.6（RTX 3060）。查找你的 GPU 架构：[CUDA GPU compute capability](https://developer.nvidia.com/cuda-gpus)。
4. `..\..\.venv\Scripts\python.exe setup.py build_ext --inplace`
5. 复制 `.pyd` 到已安装的包目录：
   `copy /y cuda_tile_rasterizer\_C*.pyd ..\..\.venv\Lib\site-packages\cuda_tile_rasterizer\cuda_tile_rasterizer\`

**编译时的临时修改**（每次编译都需要，编译后必须还原）：`setup.py` 中 `extra_compile_args` 的 `cxx` 部分把 `'-O3'` 改为 `'/O2', '/Zc:twoPhase-'` 以绕过 MSVC 兼容性问题。

GPU：NVIDIA RTX 3060 Laptop（6 GB），CUDA Toolkit 12.8，Driver 13.2

## 系统坑

- **MSYS2 sh.exe**：PATH 中的 `C:\msys64\usr\bin\sh.exe` 会把 MSVC 编译器标志（`/showIncludes` → `C:/msys64/showIncludes`）当成 POSIX 路径转换。编译 CUDA 扩展前先把它从 PATH 移除。
- **cairosvg DLL**：Cairo DLL 由 MSYS2 提供。`fit_image.py` 启动时自动搜索 `C:\msys64\{mingw64,ucrt64,clang64}\bin` 目录，找到后通过 `os.add_dll_directory()` 注册。

## 架构

```
src/forza_painter_geometrize_diffbmp/
├── __init__.py            # CUDA 检查（延迟导入 torch/cuda_tile_rasterizer）
├── fit_image.py           # CLI：fit-image → diffbmp 管线
└── generate_primitives.py # CLI：generate-primitives → PNG 文件

config/
└── default.json           # diffbmp 配置（5000 图元，300 迭代，MSE+感知损失，剪枝）

primitives/                # 生成的 PNG（28 个文件，被 gitignore）
├── circle/                # 1x1 ~ 1x5
├── square/                # 1x1 ~ 1x5
├── triangle-isosceles/    # 5x1 ~ 1x5
└── triangle-right/        # 5x1 ~ 1x5（直角在左下角）

diffbmp/                   # git 子模块 → smhongok/diffbmp
└── pydiffbmp/             # 实际的 Python 包（通过路径依赖安装）
```

## diffbmp 配置参考

默认配置在 `config/default.json`。核心参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `preprocessing.final_width` | 1080 | 输入降采样，方形裁剪 |
| `initialization.N` | 5000 | 图元数量 |
| `initialization.detail_first` | true | 动漫风格：细节在上层 |
| `optimization.num_iterations` | 300 | |
| `optimization.do_adapt_gaussian_blur` | true | sigma 2.0→0.0 |
| `optimization.loss_config` | mse + perceptual(0.3) | |
| `optimization.pruning.do_pruning` | true | 替换低透明度图元 |
| `optimization.pruning.prune_iterations` | 50 | |
| `optimization.pruning.no_prune_warmup_iterations` | 100 | |
| `primitive.output_width` | 256 | 模板分辨率 |
