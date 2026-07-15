#!/usr/bin/env bash
###############################################################################
# H2 QUICK SMOKE (run on any idle 8-GPU node that mounts /data_seoul, e.g.
# florence): AXES vs MAD only — does cross-critique (debate) beat independent
# axis critics? 20 design-forward tasks (disjoint from main1), 60k budget.
#
#   launch:  setsid nohup bash scripts/run_smoke_h2.sh >/dev/null 2>&1 &
#   watch:   tail -f logs/smoke_h2.log
#   result:  results/smoke_h2/SUMMARY.md  (AXES_vs_MAD sign test + winrates)
#
# Speed choices vs main1 (this is a DIRECTIONAL check, not evidence):
#   critic = VL-7B x3 (fast; same critics for BOTH arms -> internally fair,
#   but do not over-interpret a MAD loss: could be critic capability)
#   judge  = VL-32B (held out from this run's loop)
###############################################################################
set -e
cd /data_seoul/sunghyun/multi_obj
ROOT=$(pwd)
SUBPY=/data_seoul/sunghyun/conda_envs/subliminal/bin/python
SUBVLLM=/data_seoul/sunghyun/conda_envs/subliminal/bin/vllm
QVLLM=/data_seoul/sunghyun/conda_envs/qwen36/bin/vllm
PYFIX=$ROOT/pyfix
export XDG_CACHE_HOME=/data_seoul/sunghyun/.cache

TAG="smoke_h2"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-7B-Instruct"
JUDGE_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
BUDGET=60000
TASK_IDS=$(cat smoke_task_ids.txt)
VDIR="results/$TAG"
mkdir -p "$VDIR" logs
exec >> "logs/${TAG}.log" 2>&1
echo "================ $TAG START $(date) host=$(hostname) tasks=20 budget=$BUDGET ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py run_judge.py collect.py smoke_task_ids.txt "$VDIR/code_snapshot/"

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
wait_up(){ for i in $(seq 1 240); do up $1 && return 0; sleep 15; done
  echo "FATAL: server :$1 failed"; exit 1; }

# ---------------- PHASE A: generate (gen GPU0-3 + VL-7B critics GPU4-6) -----
killall_gpu
serve_gen 8000 0,1,2,3 --tensor-parallel-size 4 --enforce-eager
serve 8004 4 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
serve 8005 5 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
serve 8006 6 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
wait_up 8000; wait_up 8004; wait_up 8005; wait_up 8006

for arm in AXES MAD; do
  echo "======== generate $arm $(date) ========"
  $SUBPY run_generate.py --arm $arm \
    --gen-ports 8000 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004,8005,8006 --vlm-model "$CRITIC_MODEL" \
    --task-source artifacts --task-ids "$TASK_IDS" \
    --budget-tokens $BUDGET --concurrency 10 \
    --output-dir "$VDIR/$arm"
done

# ---------------- PHASE B: judge (VL-32B TP4) -------------------------------
killall_gpu
serve 8100 0,1,2,3 "$JUDGE_MODEL" --tensor-parallel-size 4 \
  --enforce-eager --limit-mm-per-prompt image=2
wait_up 8100
$SUBPY run_judge.py --run-dir "$VDIR" --judge-name qvl32 \
  --judge-ports 8100 --judge-model "$JUDGE_MODEL" \
  --axes overall,design,originality,craft --concurrency 8
killall_gpu

# ---------------- PHASE C: collect ------------------------------------------
$SUBPY collect.py "$VDIR" --judge qvl32
echo "================ $TAG DONE $(date) — see $VDIR/SUMMARY.md ================"
