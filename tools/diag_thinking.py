import json, urllib.request
PORT=24031; MODEL="Qwen/Qwen3.6-35B-A3B"
r0=open("results/strongen/r0_pool/s0/ab000004/r0.html").read()
crit=open("results/strongen/_critiques_goldfused/ab000004.txt").read()
prompt=(f"You improved this website. REQUEST: build the game.\n\nCURRENT HTML:\n{r0}\n\n"
        f"REVISION NEEDED: {crit}\n\nReturn ONLY the full improved self-contained HTML starting with <!DOCTYPE html>.")
def call(think, mt):
    body={"model":MODEL,"messages":[{"role":"user","content":prompt}],"max_tokens":mt,"temperature":0.7}
    if not think: body["chat_template_kwargs"]={"enable_thinking":False}
    req=urllib.request.Request(f"http://localhost:{PORT}/v1/chat/completions",
        data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    d=json.load(urllib.request.urlopen(req,timeout=300))
    txt=d["choices"][0]["message"]["content"]; fr=d["choices"][0].get("finish_reason")
    has=("<!DOCTYPE" in txt or "<html" in txt)
    print(f"think={think} max_tokens={mt}: len={len(txt)} finish={fr} hasHTML={has}")
    print("  head:", repr(txt[:120]))
call(True, 16384)
call(False, 16384)
