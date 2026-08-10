#!/usr/bin/env bash
#SBATCH --job-name=strongenall
#SBATCH --partition=H200,H200-ZT,H200-PCIe-ZT
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=140G
#SBATCH --time=10:00:00
#SBATCH --output=logs/strongenall_%j.log
###############################################################################
# FULL multi-round run of the strong generator (Qwen3.6-35B-A3B = gen = critic)
# on ONE H200. Reuses the SAME shared r0 as the 1-round sub-experiment
# (results/strongen/r0_pool/s0) so 1-round vs 10-round are directly comparable.
# Runs SELF/FUSED/AXES/MAD up to 10 rounds each -> results/strongenall.
# Judge = Fable, later. Unique port + server-identity check (shared-node safe).
###############################################################################
cd "${SLURM_SUBMIT_DIR:-/home2/sunghyunchoi/multi_obj}"
ROOT=$(pwd); PY=$ROOT/.venv/bin/python; VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export GEN_CONTEXT_LIMIT=49152
TAG="strongenall"; MODEL="Qwen/Qwen3.6-35B-A3B"
VDIR="results/$TAG"; SEED="s0"
R0POOL="results/strongen/r0_pool/$SEED"   # reuse the shared r0
PORT=$(( 20000 + (${SLURM_JOB_ID:-$$} % 15000) ))
while curl -s -m2 http://localhost:$PORT/v1/models >/dev/null 2>&1; do PORT=$((PORT+7)); done
mkdir -p "$VDIR" logs

ours(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q "Qwen3.6-35B-A3B"; }
wait_up(){ for i in $(seq 1 80); do ours $1 && return 0; sleep 15; done
  echo "FATAL: our server :$1 not up"; tail -40 logs/${TAG}_vllm_$1.log; exit 1; }

echo "================ $TAG START $(date) node=$(hostname) PORT=$PORT ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py cluster/run_strongenall.sh "$VDIR/code_snapshot/" 2>/dev/null || true

echo "======== serve $MODEL on :$PORT $(date) ========"
setsid env CUDA_VISIBLE_DEVICES=0 HF_HOME=$HF_HOME PATH="$ROOT/.venv/bin:$PATH" \
  $VLLM serve "$MODEL" --port $PORT --gpu-memory-utilization 0.90 \
  --max-model-len 49152 --limit-mm-per-prompt '{"image":1}' \
  --mm-processor-kwargs '{"max_pixels":2007040}' \
  > "logs/${TAG}_vllm_${PORT}.log" 2>&1 < /dev/null &
wait_up $PORT
echo "======== our server up (LOAD OK) $(date) ========"

SANITY=$(curl -s -m60 http://localhost:$PORT/v1/chat/completions -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply OK\"}],\"max_tokens\":10}" \
  2>/dev/null | $PY -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'][:40])" 2>/dev/null)
echo "SANITY GEN: '$SANITY'"
[ -z "$SANITY" ] && { echo "FATAL: sanity empty"; exit 1; }

# reuse shared r0; if missing, regenerate
if [ ! -d "$R0POOL" ] || [ "$(ls $R0POOL 2>/dev/null | wc -l)" -lt 1 ]; then
  echo "======== r0 pool (shared missing -> regen) $(date) ========"
  R0POOL="$VDIR/r0_pool/$SEED"
  $PY make_r0_pool.py --out "$R0POOL" --gen-ports $PORT --gen-model "$MODEL" --n-items 12 --concurrency 8
else
  echo "======== reusing shared r0 pool: $R0POOL ($(ls $R0POOL|wc -l) tasks) ========"
fi

for arm in SELF FUSED AXES MAD; do
  echo "======== $arm (cap 10) $(date) ========"
  $PY run_generate.py --arm $arm \
    --gen-ports $PORT --gen-model "$MODEL" \
    --vlm-ports $PORT --vlm-model "$MODEL" \
    --n-items 12 --budget-tokens 700000 --max-rounds-cap 10 \
    --init-pool "$R0POOL" \
    --max-tokens 16384 --concurrency 8 \
    --output-dir "$VDIR/$SEED/$arm"
done
echo "================ $TAG DONE $(date) ================"
