# Execution incidents

These are retained so the run is reproducible rather than appearing cleaner than it was.

1. The system Python did not include Playwright. A project-local `.gold12-venv`
   was created and Playwright Chromium was installed.
2. Initial Chromium capture attempts timed out because it tried to use GPU paths
   while both B200s were occupied by vLLM. No generated HTML was discarded.
   Chromium was switched to CPU headless mode and all 12 saved r0 HTML files were
   rendered successfully.
3. The first pairwise-judge attempt supplied two separate images, but the running
   vLLM was configured for at most one image per prompt. All 72 calls were rejected
   with HTTP 400 and produced no votes. The valid rerun concatenated A and B into
   one left/right image, explicitly declared LEFT=A and RIGHT=B, and completed
   72/72 calls. The final `pairwise_audit.json` contains only this valid rerun.
4. No external API or external judge was used. Generator, revision executor and
   automated judge were the same local Qwen3.6-27B model; this is a documented
   limitation, not held-out evidence.
