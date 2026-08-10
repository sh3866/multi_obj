#!/usr/bin/env bash
###############################################################################
# DEEP-LOOP ablation (2026-07-15, motivated by the Anthropic harness blog's
# "~20 refinement iterations, design gains around #10" observation):
#   - 15 curated tasks (deep_task_ids.txt: 9 clean pilot ids + 6 screened)
#   - round cap raised 4 -> 15 (consensus-stop unchanged: good_enough still
#     halts earlier; SELF now has its own GOOD_ENOUGH stop for fairness)
#   - budget guard 900k tokens/task (MAD at 15 rounds ~ 500-600k)
#   - run_judge --all-candidates: every stored round judged absolutely
#     -> quality-vs-round curves decide whether the main run's 4-round cap
#        truncates late design gains.
# usage: bash cluster/run_deep15.sh  (4 GPUs; sbatch via sbatch_deep15.sh)
###############################################################################
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=$ROOT/.venv/bin/python
VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export GEN_CONTEXT_LIMIT=32768

TAG="deep15"
N=15
TASK_ARGS="--task-source artifacts --task-ids $(cat deep_task_ids.txt)"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
JUDGE_OPEN="Qwen/Qwen2.5-VL-72B-Instruct"
BUDGET=900000
ROUNDS=15
VDIR="results/$TAG"
mkdir -p "$VDIR" logs

exec > >(tee -a "logs/${TAG}.log") 2>&1
echo "================ $TAG START $(date) N=$N rounds=$ROUNDS gen=$GEN_MODEL ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py run_judge.py run_checklist.py collect.py PLAN.md \
      deep_task_ids.txt cluster/run_deep15.sh "$VDIR/code_snapshot/"

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

for arm in ZS SELF FUSED AXES MAD; do
  echo "======== generate $arm $(date) ========"
  $PY run_generate.py --arm $arm \
    --gen-ports 8000,8001 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004,8005 --vlm-model "$CRITIC_MODEL" \
    $TASK_ARGS \
    --n-items "$N" --budget-tokens $BUDGET --max-rounds-cap $ROUNDS \
    --max-tokens 16384 --concurrency 10 \
    --output-dir "$VDIR/$arm"
done

# ---------------- PHASE B: held-out judge (every candidate) ----------------
# TP2 crashes with "illegal memory access" in the symm-mem/custom-allreduce
# fusion path on these H200 nodes (2026-07-15) -> eager + NCCL allreduce.
export VLLM_ALLREDUCE_USE_SYMM_MEM=0
killall_gpu
serve 8100 0,1 "$JUDGE_OPEN" --tensor-parallel-size 2 --max-model-len 16384 \
  --enforce-eager --disable-custom-all-reduce \
  --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
serve 8101 2,3 "$JUDGE_OPEN" --tensor-parallel-size 2 --max-model-len 16384 \
  --enforce-eager --disable-custom-all-reduce \
  --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8100; wait_up 8101
echo "======== absolute scoring (all candidates) $(date) ========"
$PY run_judge.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100,8101 --judge-model "$JUDGE_OPEN" \
  --all-candidates --concurrency 8
echo "======== checklist judging $(date) ========"
$PY run_checklist.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100,8101 --judge-model "$JUDGE_OPEN" \
  --all-candidates --concurrency 8
killall_gpu

# ---------------- PHASE C: collect ----------------
echo "======== collect $(date) ========"
$PY collect.py "$VDIR" --judge qvl72
$PY make_report.py "$VDIR" --judge qvl72
echo "================ $TAG DONE $(date) — see $VDIR/SUMMARY.md + REPORT.html ================"
