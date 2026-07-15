#!/usr/bin/env bash
###############################################################################
# AICluster one-time setup (run on a login/compute node with internet):
#   1) python env (uv) with vLLM (latest — H200 native FP8, Qwen3.6 supported)
#   2) playwright chromium (user-space)
#   3) model downloads -> $HF_HOME (see download_models.sh)
# Adjust ROOT if your clone lives elsewhere.
###############################################################################
set -e
ROOT="${ROOT:-$HOME/multi_obj}"
ENVDIR="$ROOT/.venv"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"

cd "$ROOT"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

uv venv "$ENVDIR" --python 3.11
source "$ENVDIR/bin/activate"
uv pip install vllm aiohttp playwright pillow numpy
python -m playwright install chromium

echo "setup done. env: source $ENVDIR/bin/activate"
echo "next: bash cluster/download_models.sh   (~240GB into \$HF_HOME)"
