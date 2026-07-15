#!/usr/bin/env bash
# Offline end-to-end smoke: 6 arms -> pairwise judge -> checklist -> collect.
# Uses the REAL ArtifactsBench dataset (design_forward, medium+hard) with mock
# clients — no GPU/servers needed.
set -e
cd "$(dirname "$0")/.."
rm -rf results/_smoke
for arm in ZS BON SELF FUSED AXES MAD; do
  python3 run_generate.py --mock --no-render --arm $arm --n-items 3 \
    --task-source artifacts --categories design_forward --difficulties medium,hard \
    --budget-tokens 12000 --output-dir results/_smoke/$arm
done
python3 run_judge.py --run-dir results/_smoke --mock --judge-name qvl72 \
  --axes overall,design
python3 run_checklist.py --run-dir results/_smoke --mock --judge-name qvl72
python3 collect.py results/_smoke --judge qvl72
echo "SMOKE OK — see results/_smoke/SUMMARY.md"
