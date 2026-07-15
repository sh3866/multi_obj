#!/usr/bin/env bash
#SBATCH -J mo_fast6
#SBATCH -p H200                 # adjust: H200 / H200-ZT / H200-PCIe per queue
#SBATCH --gres=gpu:4
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH -t 12:00:00             # adjust to partition/QoS limit
#SBATCH -o %x_%j.log
###############################################################################
# fast6 on 4x H200 — ALL servers up simultaneously (no phase swapping):
#   GPU0 gen Qwen3.6-FP8 (native FP8, ctx 32k)   :8000
#   GPU1 critic VL-32B                            :8004
#   GPU2-3 judge VL-72B TP2                       :8100
# 6 arms x 20 tasks (4-round regime) -> pairwise + checklist -> SUMMARY.md
# Estimated wall time on H200: ~1-1.5h total.
###############################################################################
set -e
ROOT="${ROOT:-$HOME/multi_obj}"
cd "$ROOT"
source .venv/bin/activate
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export GEN_CONTEXT_LIMIT=32768

TAG="${TAG:-h200_fast6}"
GEN_MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
CRITIC_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
JUDGE_MODEL="Qwen/Qwen2.5-VL-72B-Instruct"
TASK_IDS=$(cat smoke_task_ids.txt)
VDIR="results/$TAG"
mkdir -p "$VDIR" logs

up(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q '"data"'; }
wait_up(){ for i in $(seq 1 120); do up $1 && return 0; sleep 15; done
  echo "FATAL: server :$1 failed"; exit 1; }

# H200: no eager workaround needed — CUDA graphs on, native FP8
CUDA_VISIBLE_DEVICES=0 vllm serve "$GEN_MODEL" --port 8000 \
  --max-model-len 32768 --gpu-memory-utilization 0.92 \
  > logs/${TAG}_vllm_8000.log 2>&1 &
CUDA_VISIBLE_DEVICES=1 vllm serve "$CRITIC_MODEL" --port 8004 \
  --max-model-len 16384 --gpu-memory-utilization 0.92 \
  --limit-mm-per-prompt '{"image":1}' \
  > logs/${TAG}_vllm_8004.log 2>&1 &
CUDA_VISIBLE_DEVICES=2,3 vllm serve "$JUDGE_MODEL" --port 8100 \
  --tensor-parallel-size 2 --max-model-len 16384 \
  --gpu-memory-utilization 0.92 --limit-mm-per-prompt '{"image":3}' \
  > logs/${TAG}_vllm_8100.log 2>&1 &
wait_up 8000; wait_up 8004; wait_up 8100

for arm in ZS BON SELF FUSED AXES MAD DISC; do
  echo "======== generate $arm $(date) ========"
  python run_generate.py --arm $arm \
    --gen-ports 8000 --gen-model "$GEN_MODEL" \
    --vlm-ports 8004 --vlm-model "$CRITIC_MODEL" \
    --task-source artifacts --task-ids "$TASK_IDS" \
    --concurrency 16 --output-dir "$VDIR/$arm"
done

echo "======== judging $(date) ========"
python run_judge.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100 --judge-model "$JUDGE_MODEL" \
  --axes overall,design,originality,craft --concurrency 12
python run_checklist.py --run-dir "$VDIR" --judge-name qvl72 \
  --judge-ports 8100 --judge-model "$JUDGE_MODEL" \
  --all-candidates --concurrency 12
python collect.py "$VDIR" --judge qvl72
echo "================ $TAG DONE $(date) ================"
