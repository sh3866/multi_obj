"""Emit generated sites in WebGen-Bench's artifact format so its OWN scoring
scripts (ui_test_bolt = WebVoyager functionality, grade_appearance_bolt_diy =
Qwen2.5-VL appearance) consume our output unchanged.

Per task we write, under  {artifact_root}/{system}/ :
  {app}.json   bolt-style record; messages[-1].content carries the start action
  {app}.zip    runnable single-page Vite project (index.html = generated site)
  extracted/{app}/   the same project unzipped (convenience / dir-based serving)

app = f"{idx+1:06d}" aligns each artifact with the idx-th data/test.jsonl record,
which is how WebGen matches ui_instruct test cases and assigns serving ports.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from typing import Dict

from ..infra.io_utils import atomic_write_text, atomic_write_bytes

PACKAGE_JSON = {
    "name": "webgen-site",
    "private": True,
    "version": "0.0.0",
    "scripts": {"dev": "vite --host", "start": "vite --host"},
    "devDependencies": {"vite": "^5.2.0"},
}

# bolt.diy-style assistant message: the harness extracts the <boltAction type="start">.
BOLT_MESSAGE = (
    "<boltArtifact id=\"site\" title=\"Generated site\">\n"
    "<boltAction type=\"shell\">npm install</boltAction>\n"
    "<boltAction type=\"start\">npm run dev</boltAction>\n"
    "</boltArtifact>"
)


def _project_files(html: str) -> Dict[str, str]:
    return {
        "index.html": html,
        "package.json": json.dumps(PACKAGE_JSON, indent=2),
        # vite serves index.html at root; no build step needed for a static page.
    }


def write_artifact(system: str, app: str, instruction: str, html: str,
                   artifact_root: str) -> Dict[str, str]:
    sys_dir = os.path.join(artifact_root, system)
    os.makedirs(sys_dir, exist_ok=True)

    files = _project_files(html)

    # 1) zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    atomic_write_bytes(os.path.join(sys_dir, f"{app}.zip"), buf.getvalue())

    # 2) bolt-style json (start action for the serving harness)
    rec = {"id": app, "instruction": instruction,
           "messages": [{"role": "user", "content": instruction},
                        {"role": "assistant", "content": BOLT_MESSAGE}]}
    atomic_write_text(os.path.join(sys_dir, f"{app}.json"),
                      json.dumps(rec, ensure_ascii=False))

    # 3) extracted dir (convenience)
    ex = os.path.join(sys_dir, "extracted", app)
    os.makedirs(ex, exist_ok=True)
    for name, content in files.items():
        atomic_write_text(os.path.join(ex, name), content)

    return {"zip": os.path.join(sys_dir, f"{app}.zip"),
            "json": os.path.join(sys_dir, f"{app}.json"),
            "dir": ex}
