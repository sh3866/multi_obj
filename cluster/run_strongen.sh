#!/usr/bin/env bash
#SBATCH --job-name=strongen
#SBATCH --partition=H200,H200-ZT,H200-PCIe-ZT
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=140G
#SBATCH --time=06:00:00
#SBATCH --output=logs/strongen_%j.log
###############################################################################
# STRONG-GENERATOR experiment. generator = critic = Qwen3.6-35B-A3B (BF16) on
# ONE H200 (141GB -> full context). Shared r0, then SELF/FUSED/AXES/MAD one round
# each (weak critic = the model). Then holds serving + polls for hand-written
# GOLD critiques (Opus). Judge = Fable, later.
# GSAI shared nodes: pick a UNIQUE port and VERIFY the server answering is OURS
# (model id) -- a fixed :8000 raced another tenant's gemma server -> empty gens.
###############################################################################
cd "${SLURM_SUBMIT_DIR:-/home2/sunghyunchoi/multi_obj}"
ROOT=$(pwd); PY=$ROOT/.venv/bin/python; VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export GEN_CONTEXT_LIMIT=32768
TAG="strongen"; MODEL="Qwen/Qwen3.6-35B-A3B"
VDIR="results/$TAG"; SEED="s0"
PORT=$(( 20000 + (${SLURM_JOB_ID:-$$} % 15000) ))
while curl -s -m2 http://localhost:$PORT/v1/models >/dev/null 2>&1; do PORT=$((PORT+7)); done
mkdir -p "$VDIR" logs "$VDIR/_critiques_goldfused" "$VDIR/_critiques_goldaxes" "$VDIR/_critiques_goldmad"

# UP only if it answers AND serves OUR model (avoid racing another tenant's server)
ours(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q "Qwen3.6-35B-A3B"; }
wait_up(){ for i in $(seq 1 80); do ours $1 && return 0; sleep 15; done
  echo "FATAL: our server :$1 not up"; tail -40 logs/${TAG}_vllm_$1.log; exit 1; }

echo "================ $TAG START $(date) node=$(hostname) PORT=$PORT ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py make_r0_pool.py tools cluster/run_strongen.sh "$VDIR/code_snapshot/" 2>/dev/null || true

echo "======== serve $MODEL on :$PORT $(date) ========"
setsid env CUDA_VISIBLE_DEVICES=0 HF_HOME=$HF_HOME PATH="$ROOT/.venv/bin:$PATH" \
  $VLLM serve "$MODEL" --port $PORT --gpu-memory-utilization 0.90 \
  --max-model-len 32768 --limit-mm-per-prompt '{"image":1}' \
  --mm-processor-kwargs '{"max_pixels":2007040}' \
  > "logs/${TAG}_vllm_${PORT}.log" 2>&1 < /dev/null &
wait_up $PORT
echo "======== our server up (LOAD OK) $(date) ========"

# sanity: one generation must be non-empty (catches silent gen failures early)
SANITY=$(curl -s -m60 http://localhost:$PORT/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word OK\"}],\"max_tokens\":10}" \
  2>/dev/null | $PY -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'][:40])" 2>/dev/null)
echo "SANITY GEN: '$SANITY'"
if [ -z "$SANITY" ]; then echo "FATAL: sanity generation empty"; tail -40 logs/${TAG}_vllm_${PORT}.log; exit 1; fi

echo "======== shared r0 (12 tasks) $(date) ========"
$PY make_r0_pool.py --out "$VDIR/r0_pool/$SEED" \
  --gen-ports $PORT --gen-model "$MODEL" --n-items 12 --concurrency 8

for arm in SELF FUSED AXES MAD; do
  echo "======== weak $arm (1 round) $(date) ========"
  $PY run_generate.py --arm $arm \
    --gen-ports $PORT --gen-model "$MODEL" \
    --vlm-ports $PORT --vlm-model "$MODEL" \
    --n-items 12 --budget-tokens 700000 --max-rounds-cap 1 \
    --init-pool "$VDIR/r0_pool/$SEED" \
    --max-tokens 16384 --concurrency 8 \
    --output-dir "$VDIR/$SEED/$arm"
done
echo "======== WEAK ARMS DONE $(date) — r0 + weak r1 ready for inspection ========"

echo "======== GOLD phase: waiting for critiques in $VDIR/_critiques_gold* ========"
$PY tools/strongen_gold.py --gen-ports $PORT --gen-model "$MODEL" \
  --max-tokens 16384 --concurrency 8 --wait-min 240

echo "======== HOLDING (sleep) — cancel when done ========"
sleep 3000
echo "================ $TAG DONE $(date) ================"
