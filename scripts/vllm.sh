#!/usr/bin/env bash
# Serve a text LLM (generator + code critics) and a VLM (vision critics).
# 8x RTX 3090 (24GB) available. Both 7B models fit on one card each.
#
# Text generator  -> ports 8000-8003 (4 replicas, round-robin)
# Vision critic   -> ports 8004-8007 (4 replicas, round-robin)
#
# Run:  bash scripts/vllm.sh    (then wait for "Application startup complete" x8)

GEN_MODEL="Qwen/Qwen2.5-7B-Instruct"
VLM_MODEL="Qwen/Qwen2.5-VL-7B-Instruct"

CUDA_VISIBLE_DEVICES=0 vllm serve $GEN_MODEL --port 8000 --max-model-len auto &
CUDA_VISIBLE_DEVICES=1 vllm serve $GEN_MODEL --port 8001 --max-model-len auto &
CUDA_VISIBLE_DEVICES=2 vllm serve $GEN_MODEL --port 8002 --max-model-len auto &
CUDA_VISIBLE_DEVICES=3 vllm serve $GEN_MODEL --port 8003 --max-model-len auto &

CUDA_VISIBLE_DEVICES=4 vllm serve $VLM_MODEL --port 8004 --max-model-len auto &
CUDA_VISIBLE_DEVICES=5 vllm serve $VLM_MODEL --port 8005 --max-model-len auto &
CUDA_VISIBLE_DEVICES=6 vllm serve $VLM_MODEL --port 8006 --max-model-len auto &
CUDA_VISIBLE_DEVICES=7 vllm serve $VLM_MODEL --port 8007 --max-model-len auto &

wait
