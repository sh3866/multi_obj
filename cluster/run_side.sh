#!/usr/bin/env bash
#SBATCH --job-name=sidedesign
#SBATCH --partition=H200,H200-ZT,H200-PCIe-ZT
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=140G
#SBATCH --time=3-00:00:00
#SBATCH --output=logs/side_%j.log
###############################################################################
# SIDE 'design-first' experiment (subjective, no-score critics). Reuses the main
# pipeline with --design-mode (reversible). Single-page briefs, shared r0,
# 10 rounds fixed (no early stop). Arms: SELF, FUSED/AXES/MAD x design2/4/10.
# Output -> results/sideproj (main experiment untouched).
###############################################################################
cd "${SLURM_SUBMIT_DIR:-/home2/sunghyunchoi/multi_obj}"
ROOT=$(pwd); PY=$ROOT/.venv/bin/python; VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 GEN_CONTEXT_LIMIT=49152
MODEL="Qwen/Qwen3.6-35B-A3B"
TASKS="sideproj_subjective/tasks.jsonl"; VDIR="results/sideproj"; SEED="s0"
R0POOL="$VDIR/r0_pool/$SEED"
PORT=$(( 20000 + (${SLURM_JOB_ID:-$$} % 15000) ))
while curl -s -m2 http://localhost:$PORT/v1/models >/dev/null 2>&1; do PORT=$((PORT+7)); done
mkdir -p "$VDIR" logs
ours(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q "Qwen3.6-35B-A3B"; }
wait_up(){ for i in $(seq 1 80); do ours $1 && return 0; sleep 15; done; echo "FATAL server :$1"; tail -30 logs/side_vllm_$1.log; exit 1; }

echo "================ side START $(date) node=$(hostname) PORT=$PORT ================"
cp -r src run_generate.py make_r0_pool.py sideproj_subjective cluster/run_side.sh "$VDIR/" 2>/dev/null || true
setsid env CUDA_VISIBLE_DEVICES=0 HF_HOME=$HF_HOME PATH="$ROOT/.venv/bin:$PATH" \
  $VLLM serve "$MODEL" --port $PORT --gpu-memory-utilization 0.90 \
  --max-model-len 49152 --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2007040}' \
  > "logs/side_vllm_${PORT}.log" 2>&1 < /dev/null &
wait_up $PORT
echo "======== server up $(date) ========"

COMMON="--gen-ports $PORT --gen-model $MODEL --vlm-ports $PORT --vlm-model $MODEL \
  --design-mode --no-early-stop --max-rounds-cap 10 --budget-tokens 1500000 \
  --n-items 12 --artifacts-json $TASKS --task-source artifacts \
  --max-tokens 16384 --concurrency 8"

# 1) shared design r0 (one per task)
echo "======== shared r0 pool (design) $(date) ========"
$PY make_r0_pool.py $COMMON --axis-set design4 --out "$R0POOL"

# 2) arms
run() { # $1=arm $2=axisset
  echo "======== $1 / $2 $(date) ========"
  $PY run_generate.py --arm $1 --axis-set $2 $COMMON --init-pool "$R0POOL" \
      --output-dir "$VDIR/$SEED/$1_$2"
}
run SELF design4
for g in design2 design4 design10; do run FUSED $g; done
for g in design2 design4 design10; do run AXES  $g; done
for g in design2 design4 design10; do run MAD   $g; done

echo "================ side ARMS DONE $(date) ================"
# ---- keep the vLLM server alive for interactive use until walltime / scancel ----
echo "vLLM stays UP on node=$(hostname) PORT=$PORT (jobid=$SLURM_JOB_ID)."
echo "To run more experiments against it, from gsai-login:"
echo "  srun --jobid=$SLURM_JOB_ID --overlap --pty bash"
echo "  # then inside the job:"
echo "  cd $ROOT && .venv/bin/python run_generate.py --arm MAD --axis-set design4 \\"
echo "    --gen-ports $PORT --gen-model $MODEL --vlm-ports $PORT --vlm-model $MODEL \\"
echo "    --design-mode --no-early-stop --max-rounds-cap 10 --budget-tokens 1500000 \\"
echo "    --artifacts-json $TASKS --task-source artifacts --n-items 12 \\"
echo "    --max-tokens 16384 --concurrency 8 --init-pool $R0POOL --output-dir results/sideproj/s0/ADHOC"
while ours $PORT; do sleep 300; done
echo "================ side server DOWN $(date) ================"
