#!/usr/bin/env bash
#SBATCH --job-name=grab
#SBATCH --partition=A100-80GB
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=120G
#SBATCH --time=06:00:00
#SBATCH --output=logs/grab_%j.log
echo "GRABBED $(date) node=$(hostname) gpu=$CUDA_VISIBLE_DEVICES"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
sleep 21000
