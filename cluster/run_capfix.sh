#!/usr/bin/env bash
#SBATCH --job-name=capfix
#SBATCH --partition=H200,H200-ZT,H200-PCIe-ZT
#SBATCH --qos=hpgpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=140G
#SBATCH --time=10:00:00
#SBATCH --output=logs/capfix_%j.log
###############################################################################
# RE-RUN of the cap-10 experiment AFTER the critic-parse bugfix (2026-07-25).
# Root cause: critics see the PNG -> generate_vlm(), whose max_tokens was 1024;
# Qwen3.x "thinking" preamble ate the budget and truncated the JSON -> 86%
# "(no parse)". Fix keeps thinking ON (critics reason better with it) but gives
# critics max_tokens=4096 so reasoning + JSON both fit, and extract_json now
# strips <think> and recovers fields; raw excerpts logged for audit.
# A PREFLIGHT does one real thinking-on critic call and aborts if it still can't
# parse, so we never burn a 2h run on a broken config.
# Reuses the SAME shared r0 pool; output -> results/strongenall2 (old preserved).
###############################################################################
cd "${SLURM_SUBMIT_DIR:-/home2/sunghyunchoi/multi_obj}"
ROOT=$(pwd); PY=$ROOT/.venv/bin/python; VLLM=$ROOT/.venv/bin/vllm
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export GEN_CONTEXT_LIMIT=49152
TAG="strongenall2"; MODEL="Qwen/Qwen3.6-35B-A3B"
VDIR="results/$TAG"; SEED="s0"
R0POOL="results/strongen/r0_pool/$SEED"          # reuse shared r0
PORT=$(( 20000 + (${SLURM_JOB_ID:-$$} % 15000) ))
while curl -s -m2 http://localhost:$PORT/v1/models >/dev/null 2>&1; do PORT=$((PORT+7)); done
mkdir -p "$VDIR" logs
ours(){ curl -s -m3 http://localhost:$1/v1/models 2>/dev/null | grep -q "Qwen3.6-35B-A3B"; }
wait_up(){ for i in $(seq 1 80); do ours $1 && return 0; sleep 15; done
  echo "FATAL: our server :$1 not up"; tail -40 logs/${TAG}_vllm_$1.log; exit 1; }

echo "================ $TAG START $(date) node=$(hostname) PORT=$PORT ================"
mkdir -p "$VDIR/code_snapshot"; cp -r src run_generate.py cluster/run_capfix.sh "$VDIR/code_snapshot/" 2>/dev/null || true

setsid env CUDA_VISIBLE_DEVICES=0 HF_HOME=$HF_HOME PATH="$ROOT/.venv/bin:$PATH" \
  $VLLM serve "$MODEL" --port $PORT --gpu-memory-utilization 0.90 \
  --max-model-len 49152 --limit-mm-per-prompt '{"image":1}' \
  --mm-processor-kwargs '{"max_pixels":2007040}' \
  > "logs/${TAG}_vllm_${PORT}.log" 2>&1 < /dev/null &
wait_up $PORT
echo "======== our server up (LOAD OK) $(date) ========"

SANITY=$(curl -s -m60 http://localhost:$PORT/v1/chat/completions -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply OK\"}],\"max_tokens\":10}" \
  2>/dev/null | $PY -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'][:40])" 2>/dev/null)
echo "SANITY GEN: '$SANITY'"; [ -z "$SANITY" ] && { echo "FATAL: sanity empty"; exit 1; }

[ -d "$R0POOL" ] || { echo "FATAL: shared r0 pool missing at $R0POOL"; exit 1; }
echo "======== reuse shared r0: $R0POOL ($(ls $R0POOL|wc -l) tasks) ========"

echo "======== PREFLIGHT: one real thinking-on vision critic (parse?) $(date) ========"
PFPNG=$(ls results/strongenall/s0/AXES/problems/*/candidates/r0.png 2>/dev/null | head -1)
if [ -n "$PFPNG" ]; then
  PFTASK=$(echo "$PFPNG" | grep -oP 'problems/\K[^/]+')
  $PY - "$PORT" "$MODEL" "$PFPNG" "$PFTASK" <<'PYEOF'
import sys, json, asyncio
sys.path.insert(0, ".")
from src.infra.client import make_client
from src.critics import prompts
from src.infra.parse import extract_json
port, model, png, task = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
instr = json.load(open(f"results/strongenall/s0/AXES/problems/{task}/trace.json"))["instruction"]
async def main():
    c = make_client([port], model, 2, False, "vlm")
    async with c:
        p = prompts.critic_prompt("design", "Design quality: coherent whole, mood/identity.",
                                  instr, has_image=True)
        oks = 0
        for _ in range(3):
            raw = await c.generate_vlm(p, [png], max_tokens=4096, temperature=0.3)
            d = extract_json(raw)
            print(f"  parse_ok={d is not None} raw_len={len(raw or '')} think={'<think>' in (raw or '')} "
                  f"crit={str((d or {}).get('critique',''))[:80]!r}", flush=True)
            oks += int(d is not None)
        print(f"PREFLIGHT parse {oks}/3 OK", flush=True)
        sys.exit(0 if oks >= 2 else 3)
asyncio.run(main())
PYEOF
  RC=$?
  if [ $RC -eq 3 ]; then echo "FATAL: thinking-on critic still won't parse at 4096 — abort before full run"; exit 1; fi
  [ $RC -ne 0 ] && echo "WARN: preflight script error (rc=$RC) — continuing anyway"
fi

for arm in SELF FUSED AXES MAD; do
  echo "======== $arm (cap 10) $(date) ========"
  $PY run_generate.py --arm $arm \
    --gen-ports $PORT --gen-model "$MODEL" --vlm-ports $PORT --vlm-model "$MODEL" \
    --n-items 12 --budget-tokens 700000 --max-rounds-cap 10 --init-pool "$R0POOL" \
    --max-tokens 16384 --concurrency 8 --output-dir "$VDIR/$SEED/$arm"
done

echo "======== PARSE-RATE CHECK (fix 검증) $(date) ========"
$PY - <<'PYEOF'
import json, glob
tot=no=0
for f in glob.glob("results/strongenall2/s0/*/problems/*/trace.json"):
    for e in json.load(open(f)).get("history",[]):
        deb=e.get("debate") or {}
        for ax,c in (deb.get("critiques",{}) if isinstance(deb,dict) else {}).items():
            tot+=1
            if str(c.get("critique"))=="(no parse)": no+=1
print(f"AXES/MAD axis-critic parse: {tot-no}/{tot} OK ({100*(tot-no)/max(tot,1):.0f}%)  [was 14%]")
PYEOF
echo "================ $TAG DONE $(date) ================"
