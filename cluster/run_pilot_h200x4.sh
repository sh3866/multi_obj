#!/usr/bin/env bash
###############################################################################
# Phase-1 pilot on the GSAI cluster, 4x H200 (e.g. inside the n89 allocation):
#   usage:  srun --jobid=<ALLOC> bash cluster/run_pilot_h200x4.sh <tag> <n_items>
#   or on the node directly: bash cluster/run_pilot_h200x4.sh pilot1 10
#
# Uses the repo venv ($ROOT/.venv from cluster/setup_cluster.sh) and the HF
# cache in $HOME. No /data_seoul on this cluster.
#
#   PHASE A  gen Qwen3.6-35B FP8, 2 replicas (GPU0 :8000, GPU1 :8001)
#            critic VL-32B, 2 replicas (GPU2 :8004, GPU3 :8005)
#            -> 5 arms x N tasks (max-performance regime, no early stop)
#   PHASE B  judge VL-72B TP2 x2 replicas (:8100 GPU0-1, :8101 GPU2-3)
#            absolute 0-10 scoring + checklist (all candidates)
#   PHASE C  collect -> results/<tag>/SUMMARY.md
###############################################################################
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=$ROOT/.venv/bin/python
VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export GEN_CONTEXT_LIMIT=32768

TAG="${1:-pilot1}"; N="${2:-10}"; SOURCE="${3:-artifacts}"   # artifacts | webgen
if [ "$SOURCE" = "webgen" ]; then
  TASK_ARGS="--task-source webgen"
else
  # stratified 10-task subset of the curated main 60 (pilot_task_ids.txt):
  # category mix mirrors the main run, so the discrimination gate is tested
  # on the same distribution it will guard.
  TASK_ARGS="--task-source artifacts --task-ids $(cat pilot_task_ids.txt)"
fi
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"      # same tier as generator
JUDGE_OPEN="Qwen/Qwen2.5-VL-72B-Instruct"        # held-out, above both
BUDGET=250000   # runaway safety guard only (tokens reported, not matched)
VDIR="results/$TAG"
mkdir -p "$VDIR" logs
exec > >(tee -a "logs/${TAG}.log") 2>&1
echo "================ $TAG START $(date) N=$N gen=$GEN_MODEL ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py run_judge.py run_checklist.py collect.py PLAN.md \
      cluster/run_pilot_h200x4.sh "$VDIR/code_snapshot/"

up(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q '"data"'; }
serve(){ local port=$1 gpus=$2 model=$3; shift 3
  setsid env CUDA_VISIBLE_DEVICES=$gpus HF_HOME=$HF_HOME \
    PATH="$ROOT/.venv/bin:$PATH" \
    $VLLM serve "$model" --port $port --gpu-memory-utilization 0.92 "$@" \
    > "logs/${TAG}_vllm_${port}.log" 2>&1 < /dev/null & }
killall_gpu(){ pkill -9 -f "vllm serve" 2>/dev/null || true
  for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    kill -9 "$pid" 2>/dev/null || true; done; sleep 8; }
wait_up(){ for i in $(seq 1 240); do up $1 && return 0; sleep 15; done
  echo "FATAL: server :$1 failed (see logs/${TAG}_vllm_$1.log)"; exit 1; }

# ---------------- PHASE A: generate ----------------
killall_gpu
serve 8000 0 "$GEN_MODEL"    --max-model-len 32768
serve 8001 1 "$GEN_MODEL"    --max-model-len 32768
serve 8004 2 "$CRITIC_MODEL" --max-model-len 12288 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
serve 8005 3 "$CRITIC_MODEL" --max-model-len 12288 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8000; wait_up 8001; wait_up 8004; wait_up 8005

for arm in ZS SELF FUSED AXES MAD; do   # BON excluded (user decision 2026-07-15); recoverable post hoc on the same tasks
  echo "======== generate $arm $(date) ========"
  $PY run_generate.py --arm $arm \
    --gen-ports 8000,8001 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004,8005 --vlm-model "$CRITIC_MODEL" \
    $TASK_ARGS \
    --n-items "$N" --budget-tokens $BUDGET --max-tokens 16384 --concurrency 10 \
    --output-dir "$VDIR/$arm"
done

# ---------------- PHASE B: held-out judge ----------------
# TP2 crashes with "illegal memory access" in the symm-mem/custom-allreduce
# fusion path on these H200 nodes (hit on both n89 and n91, 2026-07-15).
# eager + NCCL allreduce is stable; judge phase is few-call so speed is fine.
export VLLM_ALLREDUCE_USE_SYMM_MEM=0
killall_gpu
serve 8100 0,1 "$JUDGE_OPEN" --tensor-parallel-size 2 --max-model-len 16384 \
  --enforce-eager --disable-custom-all-reduce \
  --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
serve 8101 2,3 "$JUDGE_OPEN" --tensor-parallel-size 2 --max-model-len 16384 \
  --enforce-eager --disable-custom-all-reduce \
  --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8100; wait_up 8101
echo "======== absolute scoring $(date) ========"
$PY run_judge.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100,8101 --judge-model "$JUDGE_OPEN" --concurrency 8
echo "======== checklist judging $(date) ========"
$PY run_checklist.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100,8101 --judge-model "$JUDGE_OPEN" \
  --all-candidates --concurrency 8
killall_gpu

# ---------------- PHASE C: collect ----------------
echo "======== collect $(date) ========"
# listwise exclusion (user rule 2026-07-15): a task with ANY blank/0-scored
# final in ANY arm is dropped from every summary table (keeps pairing fair)
EXCL=$($PY tools/find_broken_finals.py "$VDIR" --judge qvl72)
echo "excluded tasks: ${EXCL:-none}"
$PY collect.py "$VDIR" --judge qvl72 --exclude-tasks "$EXCL"
$PY make_report.py "$VDIR" --judge qvl72 --exclude-tasks "$EXCL"
echo "================ $TAG DONE $(date) — see $VDIR/SUMMARY.md + REPORT.html ================"
