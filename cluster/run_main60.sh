#!/usr/bin/env bash
###############################################################################
# MAIN RUN (Phase 2, launched 2026-07-15): 60 curated ArtifactsBench tasks
# x 5 arms, consensus-stop with round cap 15 (user decision: early stop is a
# bonus; cap raised from 4 after the harness-blog depth question — deep15
# provides the quality-vs-round curve on a 15-task subset).
#   - main_task_ids.txt re-curated: 7 contaminated tasks replaced
#     (Mapbox/HarmonyOS/URL-fetch/scraping/ArkTS/Eclipse), red-flag free
#   - all stop rules are explicit good_enough declarations (SELF GOOD_ENOUGH,
#     FUSED good_enough bool, AXES/MAD moderator)
#   - offline-sandbox rule stated in every generation prompt
#   - listwise auto-exclusion of blank/0-scored finals at collect time
#   - absolute judging: finals only (curves come from deep15's all-candidate
#     judging); checklist: all candidates (round curves, cheap)
# usage: sbatch cluster/sbatch_main60.sh
###############################################################################
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=$ROOT/.venv/bin/python
VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
# some compute nodes (n90) have no external DNS — vLLM's HF metadata check
# crashes the server at boot. Models are fully cached in $HF_HOME, so force
# cache-only resolution everywhere.
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export GEN_CONTEXT_LIMIT=32768

TAG="main60"
N=60
TASK_ARGS="--task-source artifacts --task-ids $(cat main_task_ids.txt)"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
JUDGE_OPEN="Qwen/Qwen2.5-VL-72B-Instruct"
BUDGET=600000
ROUNDS=8   # deep15 curve (2026-07-15): AXES/MAD peak r4-8 then degrade; cap 8
           # covers the peak and matches axisabl. Was 15 pre-deep15.
VDIR="results/$TAG"
mkdir -p "$VDIR" logs

exec > >(tee -a "logs/${TAG}.log") 2>&1
echo "================ $TAG START $(date) N=$N rounds=$ROUNDS gen=$GEN_MODEL ================"
mkdir -p "$VDIR/code_snapshot"
cp -r src run_generate.py run_judge.py run_checklist.py collect.py PLAN.md \
      main_task_ids.txt tools cluster/run_main60.sh "$VDIR/code_snapshot/"

up(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q '"data"'; }
serve(){ local port=$1 gpus=$2 model=$3; shift 3
  setsid env CUDA_VISIBLE_DEVICES=$gpus HF_HOME=$HF_HOME \
    PATH="$ROOT/.venv/bin:$PATH" \
    $VLLM serve "$model" --port $port --gpu-memory-utilization 0.92 "$@" \
    > "logs/${TAG}_vllm_${port}.log" 2>&1 < /dev/null & }
killall_gpu(){ pkill -9 -f "vllm serve" 2>/dev/null || true
  for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    kill -9 "$pid" 2>/dev/null || true; done; sleep 8; }
# simultaneous boots can race on torch.distributed's ephemeral init port
# (DistNetworkError "failed to listen", hit on n90 2026-07-15) -> stagger.
wait_up(){ for i in $(seq 1 80); do up $1 && return 0; sleep 15; done
  echo "FATAL: server :$1 failed (see logs/${TAG}_vllm_$1.log)"; exit 1; }

# ---------------- PHASE A: generate ----------------
killall_gpu
serve 8000 0 "$GEN_MODEL"    --max-model-len 32768
sleep 20
serve 8001 1 "$GEN_MODEL"    --max-model-len 32768
sleep 20
serve 8004 2 "$CRITIC_MODEL" --max-model-len 12288 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
sleep 20
serve 8005 3 "$CRITIC_MODEL" --max-model-len 12288 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8000; wait_up 8001; wait_up 8004; wait_up 8005

for arm in ZS SELF FUSED AXES MAD; do
  echo "======== generate $arm $(date) ========"
  $PY run_generate.py --arm $arm \
    --gen-ports 8000,8001 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004,8005 --vlm-model "$CRITIC_MODEL" \
    $TASK_ARGS \
    --n-items "$N" --budget-tokens $BUDGET --max-rounds-cap $ROUNDS \
    --max-tokens 16384 --concurrency 16 \
    --output-dir "$VDIR/$arm"
done

# ---------------- PHASE B: held-out judge ----------------
# TP2 crashes in the symm-mem/custom-allreduce fusion path on these H200
# nodes (2026-07-15) -> eager + NCCL allreduce.
export VLLM_ALLREDUCE_USE_SYMM_MEM=0
killall_gpu
serve 8100 0,1 "$JUDGE_OPEN" --tensor-parallel-size 2 --max-model-len 16384 \
  --enforce-eager --disable-custom-all-reduce \
  --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
sleep 20
serve 8101 2,3 "$JUDGE_OPEN" --tensor-parallel-size 2 --max-model-len 16384 \
  --enforce-eager --disable-custom-all-reduce \
  --limit-mm-per-prompt '{"image":6}' --mm-processor-kwargs '{"max_pixels":2007040}'
wait_up 8100; wait_up 8101
echo "======== absolute scoring (finals) $(date) ========"
$PY run_judge.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100,8101 --judge-model "$JUDGE_OPEN" --concurrency 8
echo "======== checklist judging (all candidates) $(date) ========"
$PY run_checklist.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100,8101 --judge-model "$JUDGE_OPEN" \
  --all-candidates --concurrency 8
killall_gpu

# ---------------- PHASE C: collect ----------------
echo "======== collect $(date) ========"
EXCL=$($PY tools/find_broken_finals.py "$VDIR" --judge qvl72)
echo "excluded tasks: ${EXCL:-none}"
$PY collect.py "$VDIR" --judge qvl72 --exclude-tasks "$EXCL"
$PY make_report.py "$VDIR" --judge qvl72 --exclude-tasks "$EXCL"
echo "================ $TAG DONE $(date) — see $VDIR/SUMMARY.md + REPORT.html ================"
