#!/usr/bin/env bash
###############################################################################
# FAST 6-ARM RUN (florence) — 4-round regime (user decision 2026-07-15):
#   every arm capped at 4 iterations (BON=4 drafts, SELF=4 refines,
#   FUSED/AXES/MAD=4 critique rounds) with self-judged early stop; tokens
#   logged, not matched. 20 design-forward tasks (smoke_task_ids.txt).
#
#   PHASE A  gen Qwen3.6 TP4 (GPU0-3 :8000) + critic VL-7B x3 (GPU4-6)
#            -> ZS BON SELF FUSED AXES MAD
#   PHASE B  judge VL-32B TP4 (:8100): pairwise 4 axes + checklist (all cands)
#   PHASE C  collect -> results/fast6/SUMMARY.md
# Launch: setsid nohup bash scripts/run_fast6.sh >/dev/null 2>&1 &
###############################################################################
set -e
cd /data_seoul/sunghyun/multi_obj
ROOT=$(pwd)
SUBPY=/data_seoul/sunghyun/conda_envs/subliminal/bin/python
SUBVLLM=/data_seoul/sunghyun/conda_envs/subliminal/bin/vllm
QVLLM=/data_seoul/sunghyun/conda_envs/qwen36/bin/vllm
PYFIX=$ROOT/pyfix
export XDG_CACHE_HOME=/data_seoul/sunghyun/.cache

TAG="fast6"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-7B-Instruct"
JUDGE_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
TASK_IDS=$(cat smoke_task_ids.txt)
VDIR="results/$TAG"
mkdir -p "$VDIR" logs
exec >> "logs/${TAG}.log" 2>&1
echo "================ $TAG START $(date) host=$(hostname) tasks=20 regime=4rounds+earlystop ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py run_judge.py run_checklist.py collect.py \
      smoke_task_ids.txt scripts/run_fast6.sh "$VDIR/code_snapshot/"

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

# ---------------- PHASE A: generate all 6 arms ----------------
killall_gpu
serve_gen 8000 0,1,2,3 --tensor-parallel-size 4 --enforce-eager
serve 8004 4 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
serve 8005 5 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
serve 8006 6 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
wait_up 8000; wait_up 8004; wait_up 8005; wait_up 8006

for arm in ZS BON SELF FUSED AXES MAD; do
  echo "======== generate $arm $(date) ========"
  $SUBPY run_generate.py --arm $arm \
    --gen-ports 8000 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004,8005,8006 --vlm-model "$CRITIC_MODEL" \
    --task-source artifacts --task-ids "$TASK_IDS" \
    --concurrency 10 \
    --output-dir "$VDIR/$arm"
done

# ---------------- PHASE B: judge ----------------
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

# ---------------- PHASE C: collect ----------------
$SUBPY collect.py "$VDIR" --judge qvl32
echo "================ $TAG DONE $(date) — see $VDIR/SUMMARY.md ================"
