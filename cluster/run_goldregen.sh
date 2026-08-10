#!/usr/bin/env bash
#SBATCH --job-name=goldregen
#SBATCH --partition=H200,H200-ZT,H200-PCIe-ZT
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=140G
#SBATCH --time=03:00:00
#SBATCH --output=logs/goldregen_%j.log
###############################################################################
# Re-generate the 36 r1_gold artifacts from the GENUINE multi-agent debate
# specs (results/strongen/_critiques_gold{fused,axes,mad}). One H200, 49152 ctx
# (so revisions of large r0 HTML do not truncate). GEN_CONTEXT_LIMIT MUST be set
# so the client sizes max_tokens correctly. Unique port + identity check.
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
wait_up(){ for i in $(seq 1 80); do ours $1 && return 0; sleep 15; done; echo "FATAL server :$1"; tail -30 logs/goldregen_vllm_$1.log; exit 1; }

echo "================ goldregen START $(date) node=$(hostname) PORT=$PORT ================"
setsid env CUDA_VISIBLE_DEVICES=0 HF_HOME=$HF_HOME PATH="$ROOT/.venv/bin:$PATH" \
  $VLLM serve "$MODEL" --port $PORT --gpu-memory-utilization 0.90 \
  --max-model-len 49152 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}' \
  > "logs/goldregen_vllm_${PORT}.log" 2>&1 < /dev/null &
wait_up $PORT
echo "======== server up (LOAD OK) $(date) ========"
$PY tools/strongen_gold.py --gen-ports $PORT --gen-model "$MODEL" \
  --max-tokens 16384 --concurrency 6 --wait-min 3
echo "================ goldregen DONE $(date) ================"
