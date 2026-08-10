#!/usr/bin/env bash
#SBATCH --job-name=goldcritic
#SBATCH --partition=H200-ZT,H200-PCIe-ZT
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=08:00:00
#SBATCH --output=logs/goldcritic_%j.log
###############################################################################
# Gold-critic single-step test: 1 GPU. Serves ONE Qwen3-VL-32B (gen), then the
# driver waits for hand-written gold critiques and revises each shared r0 ->
# r1_gold. Weak baseline (r1_weak) already in results/art32b. Judge = Fable,
# later. gen==critic model so a single server suffices on one H200.
###############################################################################
set -e
cd "${SLURM_SUBMIT_DIR:-/home2/sunghyunchoi/multi_obj}"
ROOT=$(pwd)
PY=$ROOT/.venv/bin/python
VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export GEN_CONTEXT_LIMIT=49152

TAG="goldcritic"
GEN_MODEL="Qwen/Qwen3-VL-32B-Instruct-FP8"
mkdir -p logs results/goldcritic

up(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q '"data"'; }
killall_gpu(){ pkill -9 -f "vllm serve" 2>/dev/null || true; sleep 6; }
wait_up(){ for i in $(seq 1 80); do up $1 && return 0; sleep 15; done
  echo "FATAL: server :$1 failed (see logs/${TAG}_vllm_$1.log)"; exit 1; }

echo "================ $TAG START $(date) node=$(hostname) ================"
killall_gpu
setsid env CUDA_VISIBLE_DEVICES=0 HF_HOME=$HF_HOME PATH="$ROOT/.venv/bin:$PATH" \
  $VLLM serve "$GEN_MODEL" --port 8000 --gpu-memory-utilization 0.90 \
  --max-model-len 49152 --limit-mm-per-prompt '{"image":1}' \
  --mm-processor-kwargs '{"max_pixels":2007040}' \
  > "logs/${TAG}_vllm_8000.log" 2>&1 < /dev/null &
wait_up 8000
echo "======== gen server up; running driver $(date) ========"

$PY tools/goldcritic_run.py --gen-ports 8000 --gen-model "$GEN_MODEL" \
    --max-tokens 16384 --concurrency 6 --wait-min 120

killall_gpu
echo "================ $TAG DONE $(date) ================"
