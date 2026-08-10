#!/bin/sh
#SBATCH -J mad_art30b
#SBATCH -o sbatch_log/%j.out
#SBATCH -p H200-ZT,H200-PCIe-ZT
#SBATCH -q hpgpu
#SBATCH -t 12:00:00
#SBATCH --gres=gpu:4
#SBATCH --ntasks 1
#SBATCH --cpus-per-task=16
#SBATCH --nodes=1
cd $SLURM_SUBMIT_DIR
bash cluster/run_art30b.sh
