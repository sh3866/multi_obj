"""Render one HTML file to PNG for the oracle loop (CPU headless chromium).

Usage: python tools/oracle_render.py <in.html> <out.png>
Prints 'rendered=True/False' plus any error, so the loop can spot broken frames.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.infra.render import render_and_probe

async def main():
    src, out = sys.argv[1], sys.argv[2]
    html = open(src).read()
    info = await render_and_probe(html, out, n_shots=1)
    print(f"rendered={info.get('rendered')} error={info.get('error')} "
          f"bytes={os.path.getsize(out) if os.path.exists(out) else 0}")

asyncio.run(main())
