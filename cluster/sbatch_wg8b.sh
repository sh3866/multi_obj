#!/bin/sh
#SBATCH -J mad_wg8b
#SBATCH -o sbatch_log/%j.out
#SBATCH -p H200-PCIe-ZT,H200-ZT
#SBATCH -q hpgpu
#SBATCH -t 12:00:00
#SBATCH --gres=gpu:4
#SBATCH --ntasks 1
#SBATCH --cpus-per-task=16
#SBATCH --nodes=1
cd $SLURM_SUBMIT_DIR
srun -l /bin/hostname
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
bash cluster/run_wg8b.sh
