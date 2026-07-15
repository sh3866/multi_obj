#!/usr/bin/env bash
###############################################################################
# Phase-1 pilot (PLAN.md): 6 arms x N ArtifactsBench tasks, single generator.
#   usage: bash scripts/run_pilot.sh <tag> <n_items>   (e.g. pilot1 10)
#
# Capability ladder: critic VL-32B = generator tier; judge VL-72B above both.
#   PHASE A  gen Qwen3.6-35B-A3B-FP8 TP4 (qwen36 env, GPU0-3, :8000)
#            + critic VL-32B TP4 (subliminal env, GPU4-7, :8004)
#            -> generate all 6 arms sequentially (task-source: artifacts,
#               design_forward categories, medium+hard)
#   PHASE B  kill all; judge VL-72B TP8 (GPU0-7, :8100):
#            pairwise (BT primary) + checklist (absolute, diagnostics)
#            [+ Gemini pass automatically if $GEMINI_API_KEY is set]
#   PHASE C  collect -> SUMMARY.md (gate + BT + checklist + leniency)
###############################################################################
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)
SUBPY=/data_seoul/sunghyun/conda_envs/subliminal/bin/python
SUBVLLM=/data_seoul/sunghyun/conda_envs/subliminal/bin/vllm
QVLLM=/data_seoul/sunghyun/conda_envs/qwen36/bin/vllm
PYFIX=$ROOT/pyfix
export XDG_CACHE_HOME=/data_seoul/sunghyun/.cache

TAG="${1:-pilot1}"; N="${2:-10}"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"      # same tier as generator
JUDGE_OPEN="Qwen/Qwen2.5-VL-72B-Instruct"        # held-out, above both
BUDGET=120000
VDIR="results/$TAG"
mkdir -p "$VDIR" logs
exec > >(tee -a "logs/${TAG}.log") 2>&1
echo "================ $TAG START $(date) N=$N budget=$BUDGET gen=$GEN_MODEL ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py run_judge.py run_checklist.py collect.py PLAN.md "$VDIR/code_snapshot/"

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
wait_up(){ for i in $(seq 1 180); do up $1 && return 0; sleep 10; done
  echo "server :$1 failed"; exit 1; }

# ---------------- PHASE A: generate ----------------
killall_gpu
serve_gen 8000 0,1,2,3 --tensor-parallel-size 4 --enforce-eager
serve 8004 4,5,6,7 "$CRITIC_MODEL" --tensor-parallel-size 4 --enforce-eager --limit-mm-per-prompt image=1
wait_up 8000; wait_up 8004

for arm in ZS BON SELF FUSED AXES MAD; do
  echo "---- generate $arm ----"
  $SUBPY run_generate.py --arm $arm \
    --gen-ports 8000 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004 --vlm-model "$CRITIC_MODEL" \
    --task-source artifacts --categories design_forward --difficulties medium,hard \
    --n-items $N --budget-tokens $BUDGET \
    --output-dir "$VDIR/$arm"
done

# ---------------- PHASE B: held-out judge ----------------
killall_gpu
serve 8100 0,1,2,3,4,5,6,7 "$JUDGE_OPEN" --tensor-parallel-size 8 --max-model-len 8192 --enforce-eager --limit-mm-per-prompt image=3
wait_up 8100
$SUBPY run_judge.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100 --judge-model "$JUDGE_OPEN" \
  --axes overall,design,originality,craft
$SUBPY run_checklist.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100 --judge-model "$JUDGE_OPEN"
killall_gpu

if [ -n "$GEMINI_API_KEY" ]; then
  echo "---- frontier judge (gemini) ----"
  $SUBPY run_judge.py --run-dir "$VDIR" --judge-name gemini \
    --judge-base-url https://generativelanguage.googleapis.com/v1beta/openai \
    --judge-model gemini-2.5-pro \
    --axes overall,design,originality,craft --concurrency 4
fi

# ---------------- PHASE C: collect ----------------
$SUBPY collect.py "$VDIR" --judge qvl72
echo "================ $TAG DONE $(date) — see $VDIR/SUMMARY.md ================"
