#!/usr/bin/env bash
###############################################################################
# DISC experiment on a 4-GPU node (mounts /data_seoul):
#   DISC = orchestrator imagines the ideal result (north star), DISCOVERS the
#   task-specific factor decomposition, and those factors debate (MAD machinery).
#   Same 20 tasks as fast6 -> directly comparable.
#
#   GPU layout (4x 24GB):
#     PHASE A  gen Qwen3.6-35B-FP8 TP2 (GPU0-1, :8000, ctx 16k)
#              + critic VL-7B x2 (GPU2-3, :8004-8005)
#     PHASE B  (waits for fast6 DONE on florence) judge VL-32B TP4 (:8100):
#              pairwise DISC vs MAD vs BON -> judge/results_qvl32disc.jsonl
#   Launch:  cd /data_seoul/sunghyun/multi_obj && \
#            setsid nohup bash scripts/run_disc4.sh >/dev/null 2>&1 &
#   Watch:   tail -f logs/disc4.log
###############################################################################
set -e
cd /data_seoul/sunghyun/multi_obj
SUBPY=/data_seoul/sunghyun/conda_envs/subliminal/bin/python
SUBVLLM=/data_seoul/sunghyun/conda_envs/subliminal/bin/vllm
QVLLM=/data_seoul/sunghyun/conda_envs/qwen36/bin/vllm
PYFIX=$PWD/pyfix
export XDG_CACHE_HOME=/data_seoul/sunghyun/.cache
# 16k gen context on this node (TP2 KV budget) — client adapts via default limit
TAG="disc4"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-7B-Instruct"
JUDGE_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
TASK_IDS=$(cat smoke_task_ids.txt)
VDIR="results/fast6"        # write alongside fast6 arms for joint judging
mkdir -p logs
exec >> "logs/${TAG}.log" 2>&1
echo "================ DISC START $(date) host=$(hostname) tasks=20 ================"

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

# ---------------- PHASE A: generate DISC ----------------
killall_gpu
setsid env -u LD_LIBRARY_PATH PYTHONPATH=$PYFIX XDG_CACHE_HOME=$XDG_CACHE_HOME \
  CUDA_VISIBLE_DEVICES=0,1 \
  $QVLLM serve "$GEN_MODEL" --port 8000 --gpu-memory-utilization 0.92 \
  --max-model-len 16384 --tensor-parallel-size 2 --enforce-eager \
  > "logs/${TAG}_vllm_8000.log" 2>&1 < /dev/null &
serve 8004 2 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
serve 8005 3 "$CRITIC_MODEL" --enforce-eager --limit-mm-per-prompt image=1
wait_up 8000; wait_up 8004; wait_up 8005

echo "======== generate DISC $(date) ========"
$SUBPY run_generate.py --arm DISC \
  --gen-ports 8000 --gen-model "$GEN_MODEL" \
  --vlm-ports 8004,8005 --vlm-model "$CRITIC_MODEL" \
  --task-source artifacts --task-ids "$TASK_IDS" \
  --concurrency 8 --output-dir "$VDIR/DISC"

# ---------------- PHASE B: judge DISC vs MAD vs BON ----------------
killall_gpu
echo "waiting for fast6 completion on florence (shared NFS) ..."
until grep -q "fast6 DONE" logs/fast6.log 2>/dev/null; do sleep 120; done
serve 8100 0,1,2,3 "$JUDGE_MODEL" --tensor-parallel-size 4 \
  --enforce-eager --limit-mm-per-prompt image=3
wait_up 8100
echo "======== pairwise judging DISC vs MAD vs BON $(date) ========"
$SUBPY run_judge.py --run-dir "$VDIR" --arms BON,MAD,DISC \
  --judge-name qvl32disc \
  --judge-ports 8100 --judge-model "$JUDGE_MODEL" \
  --axes overall,design,originality,craft --concurrency 8
$SUBPY run_checklist.py --run-dir "$VDIR" --arms DISC \
  --judge-name qvl32disc \
  --judge-ports 8100 --judge-model "$JUDGE_MODEL" --concurrency 8
killall_gpu
$SUBPY collect.py "$VDIR" --judge qvl32disc
echo "================ DISC DONE $(date) — see $VDIR/SUMMARY.md ================"
