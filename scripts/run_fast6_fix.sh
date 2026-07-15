#!/usr/bin/env bash
# fast6 repair: rerun the four loop arms with the context-overflow fix
# (HTML prompt cap + adaptive max_tokens), reusing already-running servers;
# then judge all 6 arms and collect.
set -e
cd /data_seoul/sunghyun/multi_obj
SUBPY=/data_seoul/sunghyun/conda_envs/subliminal/bin/python
SUBVLLM=/data_seoul/sunghyun/conda_envs/subliminal/bin/vllm
PYFIX=$PWD/pyfix
export XDG_CACHE_HOME=/data_seoul/sunghyun/.cache
TAG="fast6"; VDIR="results/$TAG"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-7B-Instruct"
JUDGE_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
TASK_IDS=$(cat smoke_task_ids.txt)
exec >> "logs/${TAG}.log" 2>&1
echo "======== FIX RERUN (context-overflow patch) $(date) ========"
cp -r src "$VDIR/code_snapshot/src_fixed" 2>/dev/null || true

up(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q '"data"'; }
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

up 8000 || { echo "FATAL: gen server not running"; exit 1; }
up 8004 || { echo "FATAL: critic server not running"; exit 1; }

for arm in SELF FUSED AXES MAD; do
  echo "======== generate $arm (fixed) $(date) ========"
  $SUBPY run_generate.py --arm $arm \
    --gen-ports 8000 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004,8005,8006 --vlm-model "$CRITIC_MODEL" \
    --task-source artifacts --task-ids "$TASK_IDS" \
    --concurrency 10 --output-dir "$VDIR/$arm"
done

killall_gpu
serve 8100 0,1,2,3 "$JUDGE_MODEL" --tensor-parallel-size 4 \
  --enforce-eager --limit-mm-per-prompt image=3
wait_up 8100
echo "======== pairwise judging $(date) ========"
$SUBPY run_judge.py --run-dir "$VDIR" --judge-name qvl32 \
  --judge-ports 8100 --judge-model "$JUDGE_MODEL" \
  --axes overall,design,originality,craft --concurrency 8
echo "======== checklist judging $(date) ========"
$SUBPY run_checklist.py --run-dir "$VDIR" --judge-name qvl32 \
  --judge-ports 8100 --judge-model "$JUDGE_MODEL" \
  --all-candidates --concurrency 8
killall_gpu
$SUBPY collect.py "$VDIR" --judge qvl32
echo "================ fast6 DONE $(date) — see $VDIR/SUMMARY.md ================"
