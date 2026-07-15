# Scoring our outputs with WebGen-Bench's own harness

We generate sites with the six arms (`run_generate.py`) into `webgen_out/<ARM>/` in
WebGen's artifact format (`{app}.zip` + `{app}.json` aligned to `data/test.jsonl`).
WebGen's **own** scripts then score functionality (WebVoyager) and appearance
(Qwen2.5-VL-32B). No human labels, no external API — everything self-hosted.

WebGen repo lives at `external/WebGen-Bench/`. Its `src/` was written for Windows;
`src-remote/` is the Linux variant — prefer that on this box.

## Prerequisites (one-time)

1. **Node.js + pm2** (serves each generated project):
   ```bash
   # install Node 20+ then:
   npm install -g pm2
   ```
2. **Playwright/Chromium** for our internal preview (generation side):
   ```bash
   pip install playwright && playwright install chromium
   ```
3. **WebVoyager env** (functional testing agent, Selenium + Chrome):
   ```bash
   cd external/WebGen-Bench
   conda create -p env/webvoyager python=3.10 -y && conda activate env/webvoyager
   cd webvoyager && pip install -r requirements.txt
   ```
4. **Serve the grader/navigator VLM = Qwen2.5-VL-32B** (OpenAI-compatible), used by
   BOTH WebVoyager (navigator) and appearance grading. On 8x RTX 3090, TP across
   ~4 cards:
   ```bash
   CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve Qwen/Qwen2.5-VL-32B-Instruct \
       --port 8100 --tensor-parallel-size 4 --max-model-len 16384 &
   ```
   GUARDRAIL: this 32B grader must differ from the S3 critic VLM (Qwen2.5-VL-7B on
   8004-7) so S3 is not optimizing the judge that scores it.

## Generate (our side)

```bash
# bring up generator + critic models
bash scripts/vllm.sh          # Qwen2.5-7B (8000-3) + Qwen2.5-VL-7B (8004-7)
for S in ZS BON SELF FUSED AXES MAD; do
    python run_generate.py --arm $S --n-items 50 \
     --categories 'User Interaction,Data Management' \
     --artifact-root webgen_out --output-dir results/main/$S
done
```

## Score (WebGen's harness) — per system

Point WebGen's functional + appearance scripts at `webgen_out/<system>` (which
contains `{app}.zip` + `{app}.json`). Using the Linux `src-remote` variants:

```bash
cd external/WebGen-Bench
# Functionality (WebVoyager) — navigator = local Qwen2.5-VL-32B on :8100
#   edit run_ui_eval_with_answer.sh: --api_model -> Qwen2.5-VL-32B, --api_base http://localhost:8100/v1
bash src/ui_test_bolt/run_ui_eval_with_answer.sh   ../../webgen_out/MAD
python src/ui_test_bolt/compute_acc.py             ../../webgen_out/MAD

# Appearance (Qwen2.5-VL-32B grades screenshots, 1-5 over 4 dims)
python src/grade_appearance_bolt_diy/get_screenshots.py  ../../webgen_out/MAD
python src/grade_appearance_bolt_diy/eval_appearance.py  ../../webgen_out/MAD   # set --model Qwen2.5-VL-32B, base :8100
python src/grade_appearance_bolt_diy/compute_grade.py    ../../webgen_out/MAD
```

(Exact flags differ slightly per WebGen version — `ui_eval_with_answer.py` hardcodes
`--api_model`/`--api_key`; replace with the local 8100 endpoint. See its `run_webvoyager()`.)

## Compare

```bash
python collect.py results/main   # + WebGen accuracy merged by hand/notebook
```
This prints compute (rounds/calls) per system and, once WebGen scores exist, merges
functionality accuracy + appearance score. Pre-registered comparisons are in PLAN.md (SELF>FUSED, FUSED>AXES=H1,
AXES>MAD=H2, BON vs MAD), read at matched compute; front metrics (`front` in
each problem's record) covers more of the (functionality × appearance) space.

## Notes / open items
- Our artifacts are single-page Vite projects (`vite --host` serves `index.html`).
  WebGen's serving (`start_service.py`) runs `npm run dev`; ensure `npm install` runs
  per task (the bolt `.json` includes a `shell: npm install` action).
- If a generated site needs richer multi-file structure for some test cases, switch
  the generator to emit a multi-file project — the artifact contract is unchanged.
