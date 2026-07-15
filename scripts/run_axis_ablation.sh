#!/usr/bin/env bash
# Axis-taxonomy ablation (MAD only, user decision 2026-07-15): after fast6
# completes, generate MAD with VisAWI axes and Lavie&Tractinsky axes on the
# same 20 tasks, then re-judge ALL arms together (incl. the two variants)
# and re-collect. Winner axis set becomes the default for the method.
set -e
cd /data_seoul/sunghyun/multi_obj
SUBPY=/data_seoul/sunghyun/conda_envs/subliminal/bin/python
SUBVLLM=/data_seoul/sunghyun/conda_envs/subliminal/bin/vllm
QVLLM=/data_seoul/sunghyun/conda_envs/qwen36/bin/vllm
PYFIX=$PWD/pyfix
export XDG_CACHE_HOME=/data_seoul/sunghyun/.cache
export GEN_CONTEXT_LIMIT=32768
TAG="fast6"; VDIR="results/$TAG"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-7B-Instruct"
JUDGE_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
TASK_IDS=$(cat smoke_task_ids.txt)
exec >> "logs/${TAG}_axis.log" 2>&1

echo "======== axis ablation armed $(date): waiting for fast6 DONE ========"
until grep -q "fast6 DONE" "logs/${TAG}.log" 2>/dev/null; do sleep 120; done
echo "======== fast6 done — starting MAD axis variants $(date) ========"

up(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q '"data"'; }
serve(){ local port=$1 gpus=$2 model=$3; shift 3
  setsid env -u LD_LIBRARY_PATH PYTHONPATH=$PYFIX XDG_CACHE_HOME=$XDG_CACHE_HOME \
    CUDA_VISIBLE_DEVICES=$gpus \
    $SUBVLLM serve $model --port $port --gpu-memory-utilization 0.92 \
    --max-model-len 12288 "$@" > "logs/${TAG}_axis_vllm_${port}.log" 2>&1 < /dev/null & }
killall_gpu(){ pkill -9 -f "vllm serve" 2>/dev/null || true
  for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    kill -9 "$pid" 2>/dev/null || true; done; sleep 8; }
wait_up(){ for i in $(seq 1 240); do up $1 && return 0; sleep 15; done
  echo "FATAL: server :$1 failed"; exit 1; }

# gen (32k ctx) + critics
killall_gpu
setsid env -u LD_LIBRARY_PATH PYTHONPATH=$PYFIX XDG_CACHE_HOME=$XDG_CACHE_HOME \
  CUDA_VISIBLE_DEVICES=0,1,2,3 \
  $QVLLM serve "$GEN_MODEL" --port 8000 --gpu-memory-utilization 0.92 \
  --max-model-len 32768 --tensor-parallel-size 4 --enforce-eager \
  > "logs/${TAG}_axis_vllm_8000.log" 2>&1 < /dev/null &
serve 8004 4 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
serve 8005 5 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
serve 8006 6 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
wait_up 8000; wait_up 8004

for SPEC in "MADVIS visawi5" "MADLT lt3"; do
  set -- $SPEC; DIR=$1; AXSET=$2
  echo "======== generate MAD/$AXSET -> $DIR $(date) ========"
  $SUBPY run_generate.py --arm MAD --axis-set $AXSET \
    --gen-ports 8000 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004,8005,8006 --vlm-model "$CRITIC_MODEL" \
    --task-source artifacts --task-ids "$TASK_IDS" \
    --concurrency 10 --output-dir "$VDIR/$DIR"
done

# re-judge everything together (8 arms incl. variants), re-collect
killall_gpu
serve 8100 0,1,2,3 "$JUDGE_MODEL" --tensor-parallel-size 4 \
  --enforce-eager --limit-mm-per-prompt image=3
wait_up 8100
echo "======== pairwise judging (all arms + variants) $(date) ========"
$SUBPY run_judge.py --run-dir "$VDIR" --judge-name qvl32 \
  --judge-ports 8100 --judge-model "$JUDGE_MODEL" \
  --axes overall,design,originality,craft --concurrency 8
echo "======== checklist judging (variants included) $(date) ========"
$SUBPY run_checklist.py --run-dir "$VDIR" --judge-name qvl32 \
  --judge-ports 8100 --judge-model "$JUDGE_MODEL" \
  --all-candidates --concurrency 8
killall_gpu
$SUBPY collect.py "$VDIR" --judge qvl32
echo "================ axis ablation DONE $(date) — see $VDIR/SUMMARY.md ================"
