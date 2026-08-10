#!/usr/bin/env bash
###############################################################################
# AXIS-TAXONOMY ablation (2026-07-15): does the literature grounding of the
# critic panel change final quality? MAD only, deep15's 15 curated tasks,
# round cap 8, consensus-stop. Three literature-grounded axis sets:
#   visawi5  — VisAWI facets (Moshagen & Thielsch 2010): simplicity/diversity/
#              colorfulness/craftsmanship + functionality anchor
#   lt3      — Lavie & Tractinsky 2004: classical/expressive + functionality
#   hedonic3 — Hassenzahl AttrakDiff: stimulation/identity + functionality
# Baseline V0 (harness-blog main4) needs NO rerun: deep15's MAD judged every
# candidate, and consensus-stop trajectories are prefix-identical, so
# V0@cap8 = deep15 candidate at min(stop_round, r8).
# Evaluation is IDENTICAL for all versions (held-out judge, harness-blog 4
# criteria) — only the in-loop panel changes.
###############################################################################
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=$ROOT/.venv/bin/python
VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export GEN_CONTEXT_LIMIT=32768

TAG="axisabl"
TASK_ARGS="--task-source artifacts --task-ids $(cat deep_task_ids.txt)"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
JUDGE_OPEN="Qwen/Qwen2.5-VL-72B-Instruct"
BUDGET=600000
ROUNDS=8
SETS="visawi5 lt3 hedonic3"
VDIR="results/$TAG"
mkdir -p "$VDIR" logs

exec > >(tee -a "logs/${TAG}.log") 2>&1
echo "================ $TAG START $(date) sets=[$SETS] rounds=$ROUNDS ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py run_judge.py collect.py deep_task_ids.txt tools \
      cluster/run_axisabl.sh "$VDIR/code_snapshot/"

up(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q '"data"'; }
serve(){ local port=$1 gpus=$2 model=$3; shift 3
  setsid env CUDA_VISIBLE_DEVICES=$gpus HF_HOME=$HF_HOME \
    PATH="$ROOT/.venv/bin:$PATH" \
    $VLLM serve "$model" --port $port --gpu-memory-utilization 0.92 "$@" \
    > "logs/${TAG}_vllm_${port}.log" 2>&1 < /dev/null & }
killall_gpu(){ pkill -9 -f "vllm serve" 2>/dev/null || true
  for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    kill -9 "$pid" 2>/dev/null || true; done; sleep 8; }
wait_up(){ for i in $(seq 1 240); do up $1 && return 0; sleep 15; done
  echo "FATAL: server :$1 failed (see logs/${TAG}_vllm_$1.log)"; exit 1; }

# ---------------- PHASE A: generate (MAD x 3 axis sets) ----------------
killall_gpu
serve 8000 0 "$GEN_MODEL"    --max-model-len 32768
serve 8001 1 "$GEN_MODEL"    --max-model-len 32768
serve 8004 2 "$CRITIC_MODEL" --max-model-len 12288 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
serve 8005 3 "$CRITIC_MODEL" --max-model-len 12288 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8000; wait_up 8001; wait_up 8004; wait_up 8005

for AXSET in $SETS; do
  echo "======== generate MAD/$AXSET $(date) ========"
  $PY run_generate.py --arm MAD --axis-set $AXSET \
    --gen-ports 8000,8001 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004,8005 --vlm-model "$CRITIC_MODEL" \
    $TASK_ARGS \
    --n-items 15 --budget-tokens $BUDGET --max-rounds-cap $ROUNDS \
    --max-tokens 16384 --concurrency 16 \
    --output-dir "$VDIR/$AXSET/MAD"
done

# ---------------- PHASE B: held-out judge (all candidates) ----------------
export VLLM_ALLREDUCE_USE_SYMM_MEM=0
killall_gpu
serve 8100 0,1 "$JUDGE_OPEN" --tensor-parallel-size 2 --max-model-len 16384 \
  --enforce-eager --disable-custom-all-reduce \
  --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
serve 8101 2,3 "$JUDGE_OPEN" --tensor-parallel-size 2 --max-model-len 16384 \
  --enforce-eager --disable-custom-all-reduce \
  --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8100; wait_up 8101
for AXSET in $SETS; do
  echo "======== absolute scoring $AXSET (all candidates) $(date) ========"
  $PY run_judge.py --run-dir "$VDIR/$AXSET" --judge-name qvl72 \
    --judge-ports 8100,8101 --judge-model "$JUDGE_OPEN" \
    --all-candidates --concurrency 8
done
killall_gpu

# ---------------- PHASE C: collect ----------------
for AXSET in $SETS; do
  echo "======== collect $AXSET $(date) ========"
  EXCL=$($PY tools/find_broken_finals.py "$VDIR/$AXSET" --judge qvl72)
  echo "excluded tasks ($AXSET): ${EXCL:-none}"
  $PY collect.py "$VDIR/$AXSET" --judge qvl72 --exclude-tasks "$EXCL"
done
echo "================ $TAG DONE $(date) ================"
