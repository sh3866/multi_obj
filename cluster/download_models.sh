#!/usr/bin/env bash
# Download the three models (~240GB total) into $HF_HOME on the cluster.
# Check your storage quota first: gen 35GB + critic 65GB + judge 145GB.
set -e
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
source "${ROOT:-$HOME/multi_obj}/.venv/bin/activate"
python - << 'EOF'
from huggingface_hub import snapshot_download
for m in ["Qwen/Qwen3.6-35B-A3B-FP8",          # generator (fits 1x H200)
          "Qwen/Qwen2.5-VL-32B-Instruct",       # critic    (1x H200)
          "Qwen/Qwen2.5-VL-72B-Instruct"]:      # judge     (2x H200 TP2)
    print("downloading", m)
    snapshot_download(m, max_workers=8)
print("ALL MODELS DOWNLOADED")
EOF
