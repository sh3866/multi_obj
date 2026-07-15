"""Tiny HTTP service exposing UIClip design-quality scoring, so the generation
loop (base env, no torch) can ground its design agent by POSTing a screenshot.

POST /score  {"png": "<abs path>", "desc": "<instruction>"}  -> {"score": float}
Run (subliminal env, one GPU):  UICLIP_DEVICE=cuda:1 python uiclip_server.py 8200
"""
import json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.signals import uiclip

DEV = os.environ.get("UICLIP_DEVICE", "cpu")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            s = uiclip.score(req.get("png", ""), req.get("desc", "")[:120], device=DEV)
        except Exception as e:
            s = 0.0
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"score": s}).encode())


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8200
    uiclip._init(DEV)                       # warm up (load model)
    print(f"UIClip server on :{port} device={DEV}", flush=True)
    HTTPServer(("127.0.0.1", port), H).serve_forever()
