#!/usr/bin/env bash
#SBATCH --job-name=sidetest
#SBATCH --partition=A100-80GB
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=140G
#SBATCH --time=01:30:00
#SBATCH --output=logs/sidetest_%j.log
###############################################################################
# SMOKE TEST of the side design experiment on 2x A100 (TP=2). 1 task, 2 rounds,
# SELF + MAD/design4 only — just verify it runs and SAVES correctly, then kill.
###############################################################################
cd "${SLURM_SUBMIT_DIR:-/home2/sunghyunchoi/multi_obj}"
ROOT=$(pwd); PY=$ROOT/.venv/bin/python; VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 GEN_CONTEXT_LIMIT=32768
MODEL="Qwen/Qwen3.6-35B-A3B"
TASKS="sideproj_subjective/tasks.jsonl"; VDIR="results/sideproj_test"; SEED="s0"
R0POOL="$VDIR/r0_pool/$SEED"
PORT=$(( 20000 + (${SLURM_JOB_ID:-$$} % 15000) ))
while curl -s -m2 http://localhost:$PORT/v1/models >/dev/null 2>&1; do PORT=$((PORT+7)); done
mkdir -p "$VDIR" logs
ours(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q "Qwen3.6-35B-A3B"; }
wait_up(){ for i in $(seq 1 90); do ours $1 && return 0; sleep 15; done; echo "FATAL server :$1"; tail -30 logs/sidetest_vllm_$1.log; exit 1; }

echo "================ sidetest START $(date) node=$(hostname) GPUs=$CUDA_VISIBLE_DEVICES PORT=$PORT ================"
setsid env HF_HOME=$HF_HOME PATH="$ROOT/.venv/bin:$PATH" \
  $VLLM serve "$MODEL" --port $PORT --tensor-parallel-size 2 --gpu-memory-utilization 0.90 \
  --max-model-len 32768 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}' \
  > "logs/sidetest_vllm_${PORT}.log" 2>&1 < /dev/null &
wait_up $PORT
echo "======== server up $(date) ========"

COMMON="--gen-ports $PORT --gen-model $MODEL --vlm-ports $PORT --vlm-model $MODEL \
  --design-mode --no-early-stop --max-rounds-cap 2 --budget-tokens 400000 \
  --n-items 1 --task-ids 4 --artifacts-json $TASKS --task-source artifacts \
  --max-tokens 12288 --concurrency 4"

echo "======== shared r0 (design) $(date) ========"
$PY make_r0_pool.py $COMMON --axis-set design4 --out "$R0POOL"
echo "======== SELF/design4 $(date) ========"
$PY run_generate.py --arm SELF --axis-set design4 $COMMON --init-pool "$R0POOL" --output-dir "$VDIR/$SEED/SELF_design4"
echo "======== MAD/design4 $(date) ========"
$PY run_generate.py --arm MAD --axis-set design4 $COMMON --init-pool "$R0POOL" --output-dir "$VDIR/$SEED/MAD_design4"
echo "================ sidetest DONE $(date) ================"
