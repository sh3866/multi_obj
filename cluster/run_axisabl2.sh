#!/usr/bin/env bash
###############################################################################
# AXIS-TAXONOMY ablation v2 — shared-r0 paired (2026-07-16):
# MAD x {visawi5, lt3, hedonic3} x 3 seeds x 15 tasks, cap 10.
# REUSES results/sharedr0/r0_pool/{s0,s1,s2} (main4-planner r0s), so all axis
# sets — including sharedr0's concurrently-running main4 MAD — start from
# IDENTICAL artifacts: differences are purely the critic panel. (The planner
# framing is main4 for everyone; uniform, hence fair.)
# Run on a second 4-GPU allocation in parallel with sharedr0.
###############################################################################
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=$ROOT/.venv/bin/python
VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export GEN_CONTEXT_LIMIT=32768

TAG="axisabl2"
TASK_ARGS="--task-source artifacts --task-ids $(cat deep_task_ids.txt)"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
JUDGE_OPEN="Qwen/Qwen2.5-VL-72B-Instruct"
BUDGET=700000
ROUNDS=10
SEEDS="s0 s1 s2"
SETS="visawi5 lt3 hedonic3"
POOL="results/sharedr0/r0_pool"
VDIR="results/$TAG"
mkdir -p "$VDIR" logs

exec > >(tee -a "logs/${TAG}.log") 2>&1
echo "================ $TAG START $(date) sets=[$SETS] seeds=[$SEEDS] rounds=$ROUNDS ================"
for SEED in $SEEDS; do
  [ -f "$POOL/$SEED/ab000001/r0.html" ] || { echo "FATAL: missing r0 pool $POOL/$SEED"; exit 1; }
done
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py run_judge.py collect.py tools deep_task_ids.txt \
      cluster/run_axisabl2.sh "$VDIR/code_snapshot/"

up(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q '"data"'; }
serve(){ local port=$1 gpus=$2 model=$3; shift 3
  setsid env CUDA_VISIBLE_DEVICES=$gpus HF_HOME=$HF_HOME \
    PATH="$ROOT/.venv/bin:$PATH" \
    $VLLM serve "$model" --port $port --gpu-memory-utilization 0.92 "$@" \
    > "logs/${TAG}_vllm_${port}.log" 2>&1 < /dev/null & }
killall_gpu(){ pkill -9 -f "vllm serve" 2>/dev/null || true
  for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    kill -9 "$pid" 2>/dev/null || true; done; sleep 8; }
wait_up(){ for i in $(seq 1 80); do up $1 && return 0; sleep 15; done
  echo "FATAL: server :$1 failed (see logs/${TAG}_vllm_$1.log)"; exit 1; }

# ---------------- PHASE A: generate ----------------
killall_gpu
serve 8010 0 "$GEN_MODEL"    --max-model-len 32768
sleep 20
serve 8011 1 "$GEN_MODEL"    --max-model-len 32768
sleep 20
serve 8014 2 "$CRITIC_MODEL" --max-model-len 12288 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
sleep 20
serve 8015 3 "$CRITIC_MODEL" --max-model-len 12288 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8010; wait_up 8011; wait_up 8014; wait_up 8015

for SEED in $SEEDS; do
  for AXSET in $SETS; do
    echo "======== generate $SEED/$AXSET $(date) ========"
    $PY run_generate.py --arm MAD --axis-set $AXSET \
      --gen-ports 8010,8011 --gen-model "$GEN_MODEL" \
      --vlm-ports 8014,8015 --vlm-model "$CRITIC_MODEL" \
      $TASK_ARGS \
      --n-items 15 --budget-tokens $BUDGET --max-rounds-cap $ROUNDS \
      --init-pool "$POOL/$SEED" \
      --max-tokens 16384 --concurrency 15 \
      --output-dir "$VDIR/$SEED/$AXSET/MAD"
  done
done

# ---------------- PHASE B: held-out judge (all candidates) ----------------
export VLLM_ALLREDUCE_USE_SYMM_MEM=0
killall_gpu
serve 8110 0,1 "$JUDGE_OPEN" --tensor-parallel-size 2 --max-model-len 16384 \
  --enforce-eager --disable-custom-all-reduce \
  --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
sleep 20
serve 8111 2,3 "$JUDGE_OPEN" --tensor-parallel-size 2 --max-model-len 16384 \
  --enforce-eager --disable-custom-all-reduce \
  --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8110; wait_up 8111
for SEED in $SEEDS; do
  for AXSET in $SETS; do
    echo "======== absolute scoring $SEED/$AXSET (all candidates) $(date) ========"
    $PY run_judge.py --run-dir "$VDIR/$SEED/$AXSET" --judge-name qvl72 \
      --judge-ports 8110,8111 --judge-model "$JUDGE_OPEN" \
      --all-candidates --concurrency 8
  done
done
killall_gpu

# ---------------- PHASE C: collect ----------------
for SEED in $SEEDS; do
  for AXSET in $SETS; do
    echo "======== collect $SEED/$AXSET $(date) ========"
    EXCL=$($PY tools/find_broken_finals.py "$VDIR/$SEED/$AXSET" --judge qvl72)
    echo "excluded ($SEED/$AXSET): ${EXCL:-none}"
    $PY collect.py "$VDIR/$SEED/$AXSET" --judge qvl72 --exclude-tasks "$EXCL"
  done
done
echo "================ $TAG DONE $(date) ================"
