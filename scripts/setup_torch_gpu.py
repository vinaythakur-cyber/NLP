"""Make PyTorch see an NVIDIA GPU when it can't. Safe to run repeatedly; never fails the launcher.

pip on Windows installs a CPU-only PyTorch by default, so an RTX card sits unused. If an NVIDIA GPU
is present but PyTorch cannot use it, this tries the official CUDA wheel indexes in turn
(oldest CUDA first: the widest driver compatibility) and keeps the first that works.
Set TORCH_CUDA_TAGS="cu126 cu128" to choose the candidates yourself, or SKIP_GPU_SETUP=1 to skip.
"""

import os
import shutil
import subprocess
import sys

TAGS = os.environ.get("TORCH_CUDA_TAGS", "cu126 cu128 cu130").split()


def cuda_ok() -> bool:
    code = "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"
    return subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0


def main() -> int:
    if os.environ.get("SKIP_GPU_SETUP"):
        return 0
    if not shutil.which("nvidia-smi"):
        print("[gpu] No NVIDIA GPU found; translation will run on the CPU.")
        return 0
    if cuda_ok():
        print("[gpu] PyTorch already uses your NVIDIA GPU.")
        return 0
    print(
        "[gpu] NVIDIA GPU found but PyTorch is CPU-only. Trying CUDA builds (several GB, one time)..."
    )
    for tag in TAGS:
        url = f"https://download.pytorch.org/whl/{tag}"
        print(f"[gpu] pip install torch from {url}")
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--force-reinstall",
                "torch",
                "--index-url",
                url,
            ]
        )
        if run.returncode == 0 and cuda_ok():
            print(f"[gpu] Success with {tag}. Your GPU will be used.")
            return 0
        print(f"[gpu] {tag} did not give a working GPU build; trying the next one.")
    print(
        "[gpu] Could not enable the GPU automatically. Translation still works on the CPU, just slower."
    )
    print(
        "[gpu] Pick the right command at https://pytorch.org/get-started/locally/ and run it in this environment."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
