#!/usr/bin/env bash
###############################################################################
# main1 repair (RUN ON EDINBURGH after main1 finishes):
#   main1 became regime-mixed when the 4-round regime landed on shared NFS
#   mid-run: BON ran under the old budget-exhaust regime (16.9 drafts) and
#   SELF ran before the context-overflow fix (~98 damaged revisions).
#   This regenerates BON + SELF under the current regime (4 iterations,
#   early stop, ctx fix), then re-judges ALL arms and re-collects.
#   usage: setsid nohup bash scripts/repair_main1.sh >/dev/null 2>&1 &
###############################################################################
set -e
cd /data_seoul/sunghyun/multi_obj
SUBPY=/data_seoul/sunghyun/conda_envs/subliminal/bin/python
SUBVLLM=/data_seoul/sunghyun/conda_envs/subliminal/bin/vllm
QVLLM=/data_seoul/sunghyun/conda_envs/qwen36/bin/vllm
PYFIX=$PWD/pyfix
export XDG_CACHE_HOME=/data_seoul/sunghyun/.cache
export GEN_CONTEXT_LIMIT=32768
TAG="main1"; VDIR="results/$TAG"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
JUDGE_OPEN="Qwen/Qwen2.5-VL-72B-Instruct"
TASK_IDS=$(cat main_task_ids.txt)
exec >> "logs/${TAG}.log" 2>&1
echo "======== REPAIR (regen BON+SELF under current regime) $(date) ========"

# wait for the original main1 script to finish everything (incl. its judge pass)
until grep -q "main1 DONE" "logs/${TAG}.log" 2>/dev/null; do sleep 300; done
echo "======== main1 finished — starting repair $(date) ========"

up(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q '"data"'; }
serve(){ local port=$1 gpus=$2 model=$3; shift 3
  setsid env -u LD_LIBRARY_PATH PYTHONPATH=$PYFIX XDG_CACHE_HOME=$XDG_CACHE_HOME \
    CUDA_VISIBLE_DEVICES=$gpus \
    $SUBVLLM serve $model --port $port --gpu-memory-utilization 0.92 \
    --max-model-len 12288 "$@" > "logs/${TAG}_repair_vllm_${port}.log" 2>&1 < /dev/null & }
killall_gpu(){ pkill -9 -f "vllm serve" 2>/dev/null || true
  for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    kill -9 "$pid" 2>/dev/null || true; done; sleep 8; }
wait_up(){ for i in $(seq 1 240); do up $1 && return 0; sleep 15; done
  echo "FATAL: server :$1 failed"; exit 1; }

killall_gpu
mv "$VDIR/BON" "$VDIR/_BON_oldregime" 2>/dev/null || true
mv "$VDIR/SELF" "$VDIR/_SELF_damaged" 2>/dev/null || true

setsid env -u LD_LIBRARY_PATH PYTHONPATH=$PYFIX XDG_CACHE_HOME=$XDG_CACHE_HOME \
  CUDA_VISIBLE_DEVICES=0,1,2,3 \
  $QVLLM serve "$GEN_MODEL" --port 8000 --gpu-memory-utilization 0.92 \
  --max-model-len 32768 --tensor-parallel-size 4 --enforce-eager \
  > "logs/${TAG}_repair_vllm_8000.log" 2>&1 < /dev/null &
serve 8004 4,5,6,7 "$CRITIC_MODEL" --tensor-parallel-size 4 \
  --enforce-eager --limit-mm-per-prompt image=1
wait_up 8000; wait_up 8004

for arm in BON SELF; do
  echo "======== regenerate $arm (current regime) $(date) ========"
  $SUBPY run_generate.py --arm $arm \
    --gen-ports 8000 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004 --vlm-model "$CRITIC_MODEL" \
    --task-source artifacts --task-ids "$TASK_IDS" \
    --concurrency 10 --output-dir "$VDIR/$arm"
done

killall_gpu
serve 8100 0,1,2,3,4,5,6,7 "$JUDGE_OPEN" --tensor-parallel-size 8 \
  --max-model-len 8192 --enforce-eager --limit-mm-per-prompt image=3
wait_up 8100
echo "======== re-judging all arms $(date) ========"
$SUBPY run_judge.py --run-dir "$VDIR" \
  --arms ZS,BON,SELF,FUSED,AXES,MAD --judge-name qvl72 \
  --judge-ports 8100 --judge-model "$JUDGE_OPEN" \
  --axes overall,design,originality,craft --concurrency 8
$SUBPY run_checklist.py --run-dir "$VDIR" \
  --arms ZS,BON,SELF,FUSED,AXES,MAD --judge-name qvl72 \
  --judge-ports 8100 --judge-model "$JUDGE_OPEN" \
  --all-candidates --concurrency 8
killall_gpu
$SUBPY collect.py "$VDIR" --judge qvl72
echo "================ main1 REPAIR DONE $(date) — see $VDIR/SUMMARY.md ================"
