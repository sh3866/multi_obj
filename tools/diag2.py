import json, urllib.request, sys
sys.path.insert(0,".")
from src.critics.prompts import revision_generation_prompt
PORT=24310; MODEL="Qwen/Qwen3.6-35B-A3B"
r0=open("results/strongen/r0_pool/s0/ab000001/r0.html").read()
crit=open("results/strongen/_critiques_goldfused/ab000001.txt").read()
prompt=revision_generation_prompt("build the puzzle game described", r0, crit)
print(f"prompt chars={len(prompt)} (~{len(prompt)//2.5:.0f} tok)")
def call(think, mt, label):
    body={"model":MODEL,"messages":[{"role":"user","content":prompt}],"max_tokens":mt,"temperature":0.7}
    if not think: body["chat_template_kwargs"]={"enable_thinking":False}
    req=urllib.request.Request(f"http://localhost:{PORT}/v1/chat/completions",
        data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    d=json.load(urllib.request.urlopen(req,timeout=400))
    ch=d["choices"][0]; txt=ch["message"]["content"]; fr=ch.get("finish_reason")
    ut=d.get("usage",{})
    print(f"[{label}] len={len(txt)} finish={fr} completion_tokens={ut.get('completion_tokens')} </html>={'</html>' in txt}")
    print(f"   end: ...{txt[-90:]!r}")
call(False, 16384, "thinkOFF mt16384")
