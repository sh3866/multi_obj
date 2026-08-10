#!/bin/sh
#SBATCH -J mad_sharedr0
#SBATCH -o sbatch_log/%j.out
#SBATCH -p H200-ZT,H200-PCIe-ZT
#SBATCH -q hpgpu
#SBATCH -t 12:00:00
#SBATCH --gres=gpu:4
#SBATCH --ntasks 1
#SBATCH --cpus-per-task=16
#SBATCH --nodes=1
# usage: sbatch [--dependency=afterany:<main60-jobid>] cluster/sbatch_sharedr0.sh
cd $SLURM_SUBMIT_DIR
srun -l /bin/hostname
srun -l /bin/date
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
bash cluster/run_sharedr0.sh
