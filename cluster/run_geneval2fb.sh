#!/usr/bin/env bash
###############################################################################
# SHARED-R0 paired design (2026-07-16): deep15's 15 tasks x 3 seeds x 4 loop
# arms (SELF/FUSED/AXES/MAD), round cap 10, main4 axes.
# Per task+seed ONE planner spec + initial html is generated once and every
# arm starts from it -> initial-draw noise (which flipped deep15 rankings)
# is removed; arm differences = pure loop differences. All candidates judged
# (quality-vs-round under pairing). SELF inherits the shared r0 too (its
# planner-free identity shifts to "self-critique loop from a given start" —
# recorded in PLAN).
###############################################################################
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=$ROOT/.venv/bin/python
VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export GEN_CONTEXT_LIMIT=32768

TAG="geneval2fb"
TASK_ARGS="--task-source artifacts --task-ids $(cat deep_task_ids.txt)"
GEN_MODEL="Qwen/Qwen3-VL-32B-Instruct-FP8"
CRITIC_MODEL="Qwen/Qwen3-VL-32B-Instruct-FP8"
JUDGE_OPEN="Qwen/Qwen3-VL-32B-Instruct-FP8"
BUDGET=700000
ROUNDS=10
SEEDS="s0"
VDIR="results/$TAG"
mkdir -p "$VDIR" logs

exec > >(tee -a "logs/${TAG}.log") 2>&1
echo "================ $TAG START $(date) seeds=[$SEEDS] rounds=$ROUNDS ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py run_judge.py make_r0_pool.py collect.py tools \
      deep_task_ids.txt cluster/run_geneval2fb.sh "$VDIR/code_snapshot/"

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

# ---------------- PHASE 0/A: r0 pools + generate ----------------
# gen == critic == Qwen3-VL-32B (blog's generator=evaluator design). VL model
# serves text-only gen requests fine; image support kept on for the critic.
MM="--limit-mm-per-prompt {\"image\":1} --mm-processor-kwargs {\"max_pixels\":2007040}"
killall_gpu
serve 8000 0 "$GEN_MODEL"    --max-model-len 32768 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
sleep 20
serve 8001 1 "$GEN_MODEL"    --max-model-len 32768 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
sleep 20
serve 8004 2 "$CRITIC_MODEL" --max-model-len 12288 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
sleep 20
serve 8005 3 "$CRITIC_MODEL" --max-model-len 12288 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8000; wait_up 8001; wait_up 8004; wait_up 8005

for SEED in $SEEDS; do
  echo "======== r0 pool $SEED $(date) ========"
  $PY make_r0_pool.py --out "$VDIR/r0_pool/$SEED" \
    --gen-ports 8000,8001 --gen-model "$GEN_MODEL" \
    $TASK_ARGS --n-items 15 --concurrency 15
done

for SEED in $SEEDS; do
  for arm in SELF FUSED AXES MAD; do
    echo "======== generate $SEED/$arm $(date) ========"
    $PY run_generate.py --arm $arm \
      --gen-ports 8000,8001 --gen-model "$GEN_MODEL" \
      --vlm-ports 8004,8005 --vlm-model "$CRITIC_MODEL" \
      $TASK_ARGS \
      --n-items 15 --budget-tokens $BUDGET --max-rounds-cap $ROUNDS \
      --init-pool "$VDIR/r0_pool/$SEED" \
      --max-tokens 16384 --concurrency 15 \
      --output-dir "$VDIR/$SEED/$arm"
  done
done

# ---------------- PHASE B: held-out judge (all candidates) ----------------
# judge = Qwen3-VL-32B (same as gen/critic; user accepts self-preference bias).
# 32B-FP8 fits one GPU -> TP1 x4 replicas for max scoring throughput.
export VLLM_ALLREDUCE_USE_SYMM_MEM=0
killall_gpu
serve 8100 0 "$JUDGE_OPEN" --max-model-len 16384 --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
sleep 20
serve 8101 1 "$JUDGE_OPEN" --max-model-len 16384 --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
sleep 20
serve 8102 2 "$JUDGE_OPEN" --max-model-len 16384 --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
sleep 20
serve 8103 3 "$JUDGE_OPEN" --max-model-len 16384 --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8100; wait_up 8101; wait_up 8102; wait_up 8103
for SEED in $SEEDS; do
  echo "======== absolute scoring $SEED (all candidates) $(date) ========"
  $PY run_judge.py --run-dir "$VDIR/$SEED" --judge-name q3vl32 \
    --judge-ports 8100,8101,8102,8103 --judge-model "$JUDGE_OPEN" \
    --all-candidates --concurrency 8
done
killall_gpu

# ---------------- PHASE C: collect ----------------
for SEED in $SEEDS; do
  echo "======== collect $SEED $(date) ========"
  EXCL=$($PY tools/find_broken_finals.py "$VDIR/$SEED" --judge q3vl32)
  echo "excluded tasks ($SEED): ${EXCL:-none}"
  $PY collect.py "$VDIR/$SEED" --judge q3vl32 --exclude-tasks "$EXCL"
done
echo "================ $TAG DONE $(date) ================"
