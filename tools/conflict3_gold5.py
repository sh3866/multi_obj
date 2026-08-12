#!/usr/bin/env python3
"""Run one auditable iterative-gold round for four selected tasks."""
import argparse, asyncio, json, shutil, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.infra.client import UsageStats, make_client
from src.infra.parse import extract_html
from src.infra.render import render_and_probe
from src.side_prompts import gen_revision_prompt

SRC=Path("results_b200/qwen4arm5_qwen36_27b")
RUN=Path("results_b200/conflict3_gold5_qwen36_27b")
TASKS=("ab000002","ab000007","ab000010","ab000012")

def wt(p,s): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding="utf-8")
def wj(p,x): wt(p,json.dumps(x,ensure_ascii=False,indent=2))

def setup():
    from src.data.artifacts_data import load_artifacts
    selected=[x for x in load_artifacts("sideproj_subjective/tasks.jsonl") if x["app"] in TASKS]
    wj(RUN/"protocol/tasks.json",selected)
    wj(RUN/"protocol/config.json",{"model":"Qwen/Qwen3.6-27B","port":8000,"temperature":0.7,"rounds":5, "axes":["spec_fidelity","unity","variety"], "judge_axes":["spec_fidelity","unity","variety","overall"], "judge_scale":"0-100","tasks":TASKS,"viewport":[1280,800],"trajectory":"each round revises immediately previous HTML"})
    for t in TASKS:
        dst=RUN/"tasks"/t/"r00";dst.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(SRC/"r0_pool"/t/"r0.html",dst/"artifact.html")
        shot=SRC/"SELF"/"problems"/t/"candidates"/"r0.png"
        if shot.exists(): shutil.copyfile(shot,dst/"screenshot.png")
    print("setup",RUN)

async def run_round(n):
    tasks={x["app"]:x for x in json.loads((RUN/"protocol/tasks.json").read_text())}
    usage=UsageStats();client=make_client([8000],"Qwen/Qwen3.6-27B",4,False,"conflict3-gold5")
    async with client as c:
      async def one(t):
        prev=RUN/"tasks"/t/f"r{n-1:02d}";out=RUN/"tasks"/t/f"r{n:02d}"
        cp=out/"critique.txt"
        if not cp.exists(): raise FileNotFoundError(cp)
        old=(prev/"artifact.html").read_text();crit=cp.read_text()
        prompt=gen_revision_prompt(tasks[t]["instruction"],old,crit);wt(out/"prompt.txt",prompt)
        generated=await c.generate_complete_html(prompt,max_tokens=16384,temperature=.7,usage_stats=usage,tag=f"iter:{t}:r{n:02d}",think=False)
        raw=generated["raw"];wt(out/"raw_response.txt",raw);new=generated["html"];wt(out/"artifact.html",new)
        probe=await render_and_probe(new,str(out/"screenshot.png"),viewport=(1280,800),full_page=False,n_shots=1,settle_ms=800) if new else {"rendered":False,"error":"no_html"}
        wj(out/"meta.json",{"task":t,"round":n,"parent":f"r{n-1:02d}","critique":crit,"raw_chars":len(raw or ""),"html_chars":len(new),"probe":probe})
        return t,probe.get("rendered",False),len(new)
      got=await asyncio.gather(*(one(t) for t in TASKS))
    wj(RUN/"protocol"/f"round_{n:02d}.json",{"created_at":time.strftime('%F %T'),"results":got,"usage":usage.to_dict()})
    print(got,usage.to_dict())

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("stage",choices=["setup","round"]);p.add_argument("--round",type=int);a=p.parse_args()
 if a.stage=="setup":setup()
 else:
  if not a.round or not 1<=a.round<=5:raise SystemExit('--round 1..5 required')
  asyncio.run(run_round(a.round))
