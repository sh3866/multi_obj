#!/bin/sh
#SBATCH -J mad_pilot
#SBATCH -o sbatch_log/%j.out
#SBATCH -p H200-ZT,H200-PCIe-ZT
#SBATCH -q hpgpu
#SBATCH -t 12:00:00
#SBATCH --gres=gpu:4
#SBATCH --ntasks 1
#SBATCH --cpus-per-task=16
#SBATCH --nodes=1
################################################################
# usage:
#   mkdir -p sbatch_log
#   sbatch cluster/sbatch_pilot.sh <tag> <n_items> [artifacts|webgen]
# examples:
#   sbatch cluster/sbatch_pilot.sh pilotA 10            # ArtifactsBench pilot
#   sbatch cluster/sbatch_pilot.sh pilotW 10 webgen     # WebGen pilot
# chain both:
#   sbatch cluster/sbatch_pilot.sh pilotA 10 && (rerun with pilotW webgen
#   via --dependency=afterok:<jobid>)
################################################################
cd $SLURM_SUBMIT_DIR

srun -l /bin/hostname
srun -l /bin/date
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader

TAG="${1:-pilotA}"; N="${2:-10}"; SOURCE="${3:-artifacts}"
bash cluster/run_pilot_h200x4.sh "$TAG" "$N" "$SOURCE"
