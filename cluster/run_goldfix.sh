#!/usr/bin/env bash
#SBATCH --job-name=goldfix
#SBATCH --partition=H200,H200-ZT,H200-PCIe-ZT
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=140G
#SBATCH --time=01:00:00
#SBATCH --output=logs/goldfix_%j.log
###############################################################################
# Re-generate 5 defective gold artifacts with a larger token budget (28672):
#   - truncated (JS cut mid-file): ab000003/goldaxes, ab000003/goldfused
#   - rendered broken (JS bug, board never draws): ab000001/goldfused,
#     ab000001/goldmad, ab000011/goldmad
# Same temp (0.7) as the other 33 -> a fresh draw under identical conditions.
# Everything else is already good and untouched.
###############################################################################
cd "${SLURM_SUBMIT_DIR:-/home2/sunghyunchoi/multi_obj}"
ROOT=$(pwd); PY=$ROOT/.venv/bin/python; VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export GEN_CONTEXT_LIMIT=49152
MODEL="Qwen/Qwen3.6-35B-A3B"
PORT=$(( 20000 + (${SLURM_JOB_ID:-$$} % 15000) ))
while curl -s -m2 http://localhost:$PORT/v1/models >/dev/null 2>&1; do PORT=$((PORT+7)); done
mkdir -p logs
ours(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q "Qwen3.6-35B-A3B"; }
wait_up(){ for i in $(seq 1 80); do ours $1 && return 0; sleep 15; done; echo "FATAL server :$1"; tail -30 logs/goldfix_vllm_$1.log; exit 1; }

echo "================ goldfix START $(date) node=$(hostname) PORT=$PORT ================"
setsid env CUDA_VISIBLE_DEVICES=0 HF_HOME=$HF_HOME PATH="$ROOT/.venv/bin:$PATH" \
  $VLLM serve "$MODEL" --port $PORT --gpu-memory-utilization 0.90 \
  --max-model-len 49152 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}' \
  > "logs/goldfix_vllm_${PORT}.log" 2>&1 < /dev/null &
wait_up $PORT
echo "======== server up (LOAD OK) $(date) ========"
$PY tools/strongen_gold.py --gen-ports $PORT --gen-model "$MODEL" \
  --only "ab000003/goldaxes,ab000003/goldfused,ab000001/goldfused,ab000001/goldmad,ab000011/goldmad" \
  --max-tokens 28672 --concurrency 3 --wait-min 3
echo "================ goldfix DONE $(date) ================"
