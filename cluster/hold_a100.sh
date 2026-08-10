#!/usr/bin/env bash
#SBATCH --job-name=a100hold
#SBATCH --partition=A100-80GB
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=140G
#SBATCH --time=24:00:00
#SBATCH --output=logs/a100hold_%j.log
###############################################################################
# Grab & HOLD one A100-80GB, then download Qwen3.6-35B-A3B and TEST-LOAD it in
# vLLM (the real gate: this is a qwen3_5_moe MoE model; our vLLM may not support
# the arch — same family as Qwen3-VL-30B-A3B-FP8 that failed to load before).
# After the test the job sleeps to keep the GPU reserved so we don't lose it.
###############################################################################
cd "${SLURM_SUBMIT_DIR:-/home2/sunghyunchoi/multi_obj}"
ROOT=$(pwd); VLLM=$ROOT/.venv/bin/vllm; HF=$ROOT/.venv/bin/hf
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_DISABLE_XET=1
MODEL="Qwen/Qwen3.6-35B-A3B"
mkdir -p logs
echo "================ a100hold START $(date) node=$(hostname) ================"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null

echo "======== download $MODEL $(date) ========"
if [ -d "$HF_HOME/hub/models--${MODEL/\//--}" ]; then
  echo "already cached"
else
  HF_HUB_OFFLINE=0 "$HF" download "$MODEL" > logs/a100hold_dl.log 2>&1 \
    && echo "download OK" || echo "download FAILED (see a100hold_dl.log; tail:)" && tail -5 logs/a100hold_dl.log
fi

echo "======== vLLM TEST-LOAD $(date) ========"
export HF_HUB_OFFLINE=1
setsid env CUDA_VISIBLE_DEVICES=0 HF_HOME=$HF_HOME PATH="$ROOT/.venv/bin:$PATH" \
  "$VLLM" serve "$MODEL" --port 8000 --gpu-memory-utilization 0.95 \
  --max-model-len 8192 --limit-mm-per-prompt '{"image":1}' \
  > logs/a100hold_vllm.log 2>&1 < /dev/null &
RESULT="TIMEOUT"
for i in $(seq 1 80); do
  if curl -s -m3 http://localhost:8000/v1/models 2>/dev/null | grep -q '"data"'; then
    RESULT="LOAD_OK"; break; fi
  if grep -qiE "not supported|no module|traceback|size of tensor|error loading|valueerror|runtimeerror" logs/a100hold_vllm.log; then
    RESULT="LOAD_ERROR"; break; fi
  sleep 15
done
echo "======== TEST-LOAD RESULT: $RESULT ($(date)) ========"
echo "---- vllm log tail ----"; tail -30 logs/a100hold_vllm.log

echo "======== HOLDING A100 (sleep) — cancel this job when done ========"
sleep 80000
