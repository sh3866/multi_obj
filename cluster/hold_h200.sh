#!/usr/bin/env bash
#SBATCH --job-name=h200hold
#SBATCH --partition=H200,H200-ZT,H200-PCIe-ZT
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=140G
#SBATCH --time=08:00:00
#SBATCH --output=logs/h200hold_%j.log
###############################################################################
# Grab & HOLD two H200, resume the Qwen3.6-35B-A3B download (shared cache), and
# TEST-LOAD it in vLLM (arch Qwen3_5MoeForConditionalGeneration is registered in
# our vLLM 0.25.1, so this should work; BF16 avoids the MoE-FP8 loader bug).
# H200 = 141GB each, so BF16 (~70GB) + long context fits easily on one GPU.
# After the test the job sleeps to keep both GPUs reserved.
###############################################################################
cd "${SLURM_SUBMIT_DIR:-/home2/sunghyunchoi/multi_obj}"
ROOT=$(pwd); VLLM=$ROOT/.venv/bin/vllm; HF=$ROOT/.venv/bin/hf
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_DISABLE_XET=1
MODEL="Qwen/Qwen3.6-35B-A3B"
mkdir -p logs
echo "================ h200hold START $(date) node=$(hostname) ================"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader 2>/dev/null

echo "======== resume download $MODEL $(date) ========"
HF_HUB_OFFLINE=0 "$HF" download "$MODEL" > logs/h200hold_dl.log 2>&1 \
  && echo "download OK" || { echo "download FAILED — tail:"; tail -6 logs/h200hold_dl.log; }
du -sh "$HF_HOME/hub/models--Qwen--Qwen3.6-35B-A3B" 2>/dev/null

echo "======== vLLM TEST-LOAD (1 replica on GPU0) $(date) ========"
export HF_HUB_OFFLINE=1
setsid env CUDA_VISIBLE_DEVICES=0 HF_HOME=$HF_HOME PATH="$ROOT/.venv/bin:$PATH" \
  "$VLLM" serve "$MODEL" --port 8000 --gpu-memory-utilization 0.90 \
  --max-model-len 32768 --limit-mm-per-prompt '{"image":1}' \
  > logs/h200hold_vllm.log 2>&1 < /dev/null &
RESULT="TIMEOUT"
for i in $(seq 1 80); do
  if curl -s -m3 http://localhost:8000/v1/models 2>/dev/null | grep -q '"data"'; then
    RESULT="LOAD_OK"; break; fi
  if grep -qiE "not supported|no module|traceback|size of tensor|error loading|valueerror|runtimeerror|out of memory" logs/h200hold_vllm.log; then
    RESULT="LOAD_ERROR"; break; fi
  sleep 15
done
echo "======== TEST-LOAD RESULT: $RESULT ($(date)) ========"
echo "---- vllm log tail ----"; tail -30 logs/h200hold_vllm.log

echo "======== HOLDING 2x H200 (sleep) — cancel this job when done ========"
sleep 25000
