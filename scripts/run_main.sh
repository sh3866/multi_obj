#!/usr/bin/env bash
###############################################################################
# MAIN experiment (PLAN.md Phase 2, 6-arm comparison):
#   60 pre-selected ArtifactsBench tasks (main_task_ids.txt: 50 design_forward
#   + 10 low_freedom contrast, medium+hard, stratified) x 6 arms x 120k budget.
#   usage: bash scripts/run_main.sh <tag>          (default: main1)
#
#   PHASE A  gen Qwen3.6-35B FP8 TP4 (qwen36, GPU0-3, :8000)
#            + critic VL-32B TP4 (subliminal, GPU4-7, :8004) -> 6 arms
#   PHASE B  judge VL-72B TP8 (GPU0-7, :8100):
#            pairwise 4 axes + checklist (final + all candidates)
#   PHASE C  collect -> results/<tag>/SUMMARY.md
# Fully detached-safe: run with `setsid nohup bash scripts/run_main.sh tag &`.
###############################################################################
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)
SUBPY=/data_seoul/sunghyun/conda_envs/subliminal/bin/python
SUBVLLM=/data_seoul/sunghyun/conda_envs/subliminal/bin/vllm
QVLLM=/data_seoul/sunghyun/conda_envs/qwen36/bin/vllm
PYFIX=$ROOT/pyfix
export XDG_CACHE_HOME=/data_seoul/sunghyun/.cache

TAG="${1:-main1}"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
JUDGE_OPEN="Qwen/Qwen2.5-VL-72B-Instruct"
BUDGET=120000
TASK_IDS=$(cat main_task_ids.txt)
VDIR="results/$TAG"
mkdir -p "$VDIR" logs
exec >> "logs/${TAG}.log" 2>&1
echo "================ $TAG START $(date) tasks=60 budget=$BUDGET gen=$GEN_MODEL ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py run_judge.py run_checklist.py collect.py PLAN.md \
      main_task_ids.txt scripts/run_main.sh "$VDIR/code_snapshot/"

up(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q '"data"'; }
serve_gen(){ local port=$1 gpus=$2; shift 2
  setsid env -u LD_LIBRARY_PATH PYTHONPATH=$PYFIX XDG_CACHE_HOME=$XDG_CACHE_HOME \
    CUDA_VISIBLE_DEVICES=$gpus \
    $QVLLM serve "$GEN_MODEL" --port $port --gpu-memory-utilization 0.92 \
    --max-model-len 16384 "$@" > "logs/${TAG}_vllm_${port}.log" 2>&1 < /dev/null & }
serve(){ local port=$1 gpus=$2 model=$3; shift 3
  setsid env -u LD_LIBRARY_PATH PYTHONPATH=$PYFIX XDG_CACHE_HOME=$XDG_CACHE_HOME \
    CUDA_VISIBLE_DEVICES=$gpus \
    $SUBVLLM serve $model --port $port --gpu-memory-utilization 0.92 \
    --max-model-len 12288 "$@" > "logs/${TAG}_vllm_${port}.log" 2>&1 < /dev/null & }
killall_gpu(){ pkill -9 -f "vllm serve" 2>/dev/null || true
  for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    kill -9 "$pid" 2>/dev/null || true; done; sleep 8; }
wait_up(){ for i in $(seq 1 240); do up $1 && return 0; sleep 15; done; return 1; }

# ---------------- PHASE A: generate ----------------
killall_gpu
serve_gen 8000 0,1,2,3 --tensor-parallel-size 4 --enforce-eager
serve 8004 4,5,6,7 "$CRITIC_MODEL" --tensor-parallel-size 4 --enforce-eager --limit-mm-per-prompt image=1
wait_up 8000 || { echo "FATAL: gen server failed"; exit 1; }
wait_up 8004 || { echo "FATAL: critic server failed"; exit 1; }

for arm in ZS BON SELF FUSED AXES MAD; do
  echo "======== generate $arm $(date) ========"
  $SUBPY run_generate.py --arm $arm \
    --gen-ports 8000 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004 --vlm-model "$CRITIC_MODEL" \
    --task-source artifacts --task-ids "$TASK_IDS" \
    --budget-tokens $BUDGET --concurrency 10 \
    --output-dir "$VDIR/$arm"
done

# ---------------- PHASE B: held-out judge ----------------
killall_gpu
serve 8100 0,1,2,3,4,5,6,7 "$JUDGE_OPEN" --tensor-parallel-size 8 --max-model-len 8192 --enforce-eager --limit-mm-per-prompt image=3
if ! wait_up 8100; then
  echo "VL-72B failed to start — retrying with enforce-eager + shorter context"
  killall_gpu
  serve 8100 0,1,2,3,4,5,6,7 "$JUDGE_OPEN" --tensor-parallel-size 8 \
    --max-model-len 4096 --enforce-eager
  wait_up 8100 || { echo "FATAL: judge server failed"; exit 1; }
fi
echo "======== pairwise judging $(date) ========"
$SUBPY run_judge.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100 --judge-model "$JUDGE_OPEN" \
  --axes overall,design,originality,craft --concurrency 8
echo "======== checklist judging $(date) ========"
$SUBPY run_checklist.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100 --judge-model "$JUDGE_OPEN" \
  --all-candidates --concurrency 8
killall_gpu

# ---------------- PHASE C: collect ----------------
echo "======== collect $(date) ========"
$SUBPY collect.py "$VDIR" --judge qvl72
echo "================ $TAG DONE $(date) — see $VDIR/SUMMARY.md ================"
