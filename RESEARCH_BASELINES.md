# Baselines & 평가 프로토콜 — 문헌 조사 결과 (2026-07-13)

deep research (104 agents, 22 sources, 25 claims 3-vote 검증, 24 confirmed / 1 refuted) 기반.
가설: H1 = 축 분리(objective별 전담 critic), H2 = debate 상호작용, H3 = Pareto front 출력.

## 0. 판을 결정하는 발견

**H2(debate)에 대한 부정 증거가 강력하고, 서로 독립적으로 3번 재현됐다.**
전부 objective 태스크(수학/QA/코드/논리)이고, **주관적 multi-objective 생성에서는 아무도
검증한 적이 없다** — 이것이 이 연구의 기회(미검증 영역)이자 부담(아래 baseline들을
token-matched로 이겨야만 주장이 성립).

| 논문 | 발견 | 우리에게 의미 |
|---|---|---|
| Zhang et al. 2025, "Stop Overvaluing MAD" ([2502.08788](https://arxiv.org/abs/2502.08788)) | 5개 MAD 방법 × 9 벤치마크 × 4 모델, 동일 inference budget(~6 calls)에서 CoT/Self-Consistency를 못 이김 (36개 구성 중 ANOVA 유의 승리 ~15%, Multi-Persona는 0%). 라운드/에이전트 증가도 무효. **단, Heter-MAD(이종 모델)는 CoT 대비 최대 +5.8%** | compute-matched CoT/SC baseline은 협상 불가. 모델 heterogeneity ablation 포함 |
| Smit et al., ICML 2024 ([2311.17371](https://arxiv.org/abs/2311.17371)) | 의료 QA 4종에서 MAD가 SC/ensembling을 일관되게 못 이김. **단 agreement intensity 튜닝 시 Multi-Persona +15%** (최하위→최상위) | MAD 열세의 상당 부분이 하이퍼파라미터 민감성. 모든 arm 튜닝 + agreement intensity를 명시적 ablation으로 |
| Huang et al., ICLR 2024 ([2310.01798](https://arxiv.org/pdf/2310.01798)) | compute-matched에서 MAD(9 responses) 83.0% < SC(9) 88.2% (GSM8K). **intrinsic self-correction은 성능을 깎음** (GPT-4 GSM8K 95.5→89.0, GPT-3.5 CSQA 75.8→41.8). 외부 신호(코드 실행 등) 있을 때만 self-correction이 작동 | critic feedback은 반드시 외부 신호(렌더 스크린샷·실측 지표)에 grounding. oracle label이 루프에 새면 안 됨 |
| 2511.07784 (2025.11, preprint) | 6-factor 통제 실험: debate 깊이/순서/confidence 노출 등 구조 파라미터는 유의하지 않음 (depth OLS 0.019, n.s.). base model 강도(β=0.600, p<0.001)와 팀 diversity가 지배적. 천장은 최강 참가자에 bounded | base model을 arm 간 고정하고 보고. 이득을 "debate"에 귀속하기 전에 diversity·모델강도 confound 분리 |

**H1(축 분리)에는 긍정 증거가 있다:**

| 논문 | 발견 | 우리에게 의미 |
|---|---|---|
| ChatEval, ICLR 2024 ([2308.07201](https://arxiv.org/abs/2308.07201)) | evaluator-인간 일치 53.8→60.0 (ChatGPT). **ablation: 같은 role이면 single과 동률(53.8), diverse role이 이득의 원천. debate turns 증가는 무의미. 3-4 agents가 peak** | 이득 메커니즘 = role 분리 (H1 지지), turns (H2 부분 부정). 단 ChatEval의 role은 generic persona — **objective별 criteria 분리는 미검증 = 우리 갭** |
| Branch-Solve-Merge, NAACL 2024 ([2310.15123](https://arxiv.org/abs/2310.15123)) | criteria별 병렬 분해(상호작용 없음)로 human-LLM agreement 최대 26% 상대 개선(약한 judge 기준; GPT-4 judge는 ~3-5%), length/position bias 최대 50% 감소 | **"axis-separated critics WITHOUT debate" arm의 직접 선례** — MAD가 반드시 이겨야 할 대조군. frontier judge일수록 분리 이득이 줄어드는 패턴 예상 |

**H3(front 출력) 선례:**
- QDAIF, ICLR 2024 ([2310.13032](https://arxiv.org/abs/2310.13032)): LLM을 mutation+evaluator로 쓰는 QD 탐색, 주관적 텍스트 도메인에서 non-QD 대비 coverage·quality 우위 (human eval 확인). **H3는 naive best-of-N이 아니라 이것을 이겨야 함.** 웹/UI·상충 objective에는 미적용 → 우리가 확장하는 것 자체가 novelty
- MOME, GECCO 2022 ([2202.03057](https://arxiv.org/abs/2202.03057)): niche별 Pareto front를 유지하는 최초 MOQD 알고리즘 — front 평가 vocabulary(MOQD score/HV)의 출처
- Design Galleries, SIGGRAPH 1997 + parallel prototyping (Dow et al., CHI 2011): "단일 최적점이 아니라 지각적으로 다른 대안들의 갤러리 제시"의 HCI 선례 — H3 동기의 인용 근거

## 1. 필수 baseline 목록 (우선순위)

### P1 — 이것 없이는 논문이 성립 안 됨
1. **Compute-matched best-of-N / Self-Consistency** (Zhang, Huang): 모든 arm과 총 token/call 일치. 결과는 quality-vs-token 곡선으로 보고
2. **Self-Refine형 single-agent loop**: 약할 것으로 예상(Huang — 외부 피드백 없는 self-critique는 해로움)이지만, "외부/분리 피드백의 가치"를 분리하는 데 필요
3. **Fused evaluator loop**: 모든 기준을 한 judge가 한 번에 — WebGen-Bench 자체의 GPT-4o rubric 채점(아래)이 실존하는 fused multi-criteria evaluator라 스토리가 자연스러움
4. **BSM형 axis-separated critics, no debate**: H1과 H2를 분리하는 핵심 대조군
5. **ChatEval형 MAD** (diverse roles, moderator): 기존 MAD-evaluator 구현의 재현

### P2 — 주장 방어에 필요
6. **Agreement-intensity 튜닝 MAD** (Smit): 알려진 가장 강한 MAD 구성. 비교 공정성을 위해 non-MAD arm도 동등 튜닝
7. **QDAIF형 QD search** (debate 없는 diversity 기계): H3의 진짜 대조군
8. **Heter-MAD** (critic마다 다른 모델): 유일하게 MAD를 구제한 변형 (Zhang)

### P3 — 여유 되면
9. MOME형 multi-objective QD (LLM operator + niche별 front)
10. WebGen-Instruct SFT (Qwen2.5-Coder-32B ft, 38.2%): inference-time 방법과 직교하는 참고선

주의: DebateLLM repo(instadeepai)가 6개 시스템을 바로 실행 가능하게 제공한다는 주장은
검증에서 0-3으로 **반박됨** — 코드 재사용 전 직접 감사할 것.

## 2. 평가 인프라 (영역 3)

- **WebGen-Bench** ([2505.03733](https://arxiv.org/abs/2505.03733)): functionality = 647 수작업 test case를 WebVoyager agent가 실행; appearance = GPT-4o가 스크린샷을 1-5 rubric(Successful Rendering / Content Relevance / Layout Harmony / Modernness & Beauty)으로 채점. SOTA(Bolt.diy+DeepSeek-R1) 27.8% → headroom 큼. 3 major / 13 minor 카테고리
- **ArtifactsBench** ([2507.04952](https://arxiv.org/abs/2507.04952)): 1,825 tasks, 렌더링+시간축 스크린샷, checklist-guided MLLM judge. WebDev Arena와 ranking consistency 94.4%, 인간 전문가 pairwise 일치 >90% → **보조 벤치마크 + 자동 pairwise judge 프로토콜의 근거**
- **UIClip**, UIST 2024 ([2404.12500](https://arxiv.org/abs/2404.12500)): screenshot+description → design quality score. 12명 디자이너 순위와 최고 일치. 인간 pairwise 판단으로 학습된 data-driven 지표 → design axis의 grounded 신호 (이미 우리 인프라에 있음)
- **Computational aesthetics** (Miniukovich & De Angeli, CHI 2015): 8개 자동 GUI 미학 지표. 웹페이지 미학 평점 분산의 **최대 49%만 설명** → 자동 지표의 ceiling이 절반 — **최종 주장에 human eval이 필수라는 인용 근거**

## 3. Human eval 프로토콜 (영역 4)

- **Blind pairwise + Bradley-Terry** (Chatbot Arena, [2403.04132](https://arxiv.org/pdf/2403.04132)): Elo 대신 BT 계수(순서 독립, 통계 추정에 우월). crowd-expert 일치 72-83% ≈ expert 간 일치(79-90%) → 크라우드 평가 유효. 비슷한 실력 쌍에 표를 집중하는 adaptive sampling으로 예산 절약
- **기준별 분리 판정** (van der Lee et al., NLG best practice): 단일 종합 점수가 아니라 axis별로 수집 — **이 권고 자체가 H1의 인용 근거가 됨**. ranking/pairwise > Likert. 시스템 여러 개 비교 시 TrueSkill 집계
- **통계 위생** (Schuff et al.): 사전 power analysis(≥0.80), <50명은 underpowered / 100+ 권장, H1·H2·H3 동시 검정 시 다중비교 보정(Holm-Bonferroni 등), IAA 보고 (NLG 논문의 12.5%만 보고하는 흔한 구멍)

## 4. 프로토콜 권고 종합

1. **보고 형식**: 고정-라운드 비교 금지, quality-vs-token 곡선. arm 간 base model 고정 + heterogeneity ablation 1개
2. **튜닝 공정성**: 모든 arm 하이퍼파라미터 튜닝 (agreement intensity 포함). critic 수는 3-4 (ChatEval peak, 5부터 하락)
3. **Ablation 분리**: debate turns (문헌 예측: flat) vs 축 개수/분리 (문헌 예측: 도움) — 이 2×2가 H1/H2 분해의 핵심
4. **Grounding**: critic 피드백은 외부 신호(렌더 스크린샷, 실측 func/efficiency, UIClip)에 anchoring. intrinsic self-judgment 단독 금지. oracle(외부 채점기) label이 refinement loop에 새면 안 됨
5. **H3 평가**: hypervolume/coverage (MOQD 계열) + 후보 budget 일치 + human pairwise로 front 유용성 확인
6. **최종 검증**: 자동 지표(WebGen 채점, UIClip, ArtifactsBench judge)는 스크리닝, 최종 주장은 blind pairwise human study (BT 집계, 사전 등록된 power/보정)

## 5. 남은 조사 과제 (openQuestions)

- objective 태스크에서의 MAD 실패가 주관적·상충 objective 생성으로 전이되는가 — 검증된 논문 없음 (= 우리의 core bet)
- 노이즈 있는 judge 점수 위에서 어떤 front metric(HV vs MOQD vs coverage)이 의미를 유지하는가
- Heter-MAD·agreement intensity가 디자인 도메인에서 debate를 구제하는지, 그리고 그것을 H1 효과와 factorial하게 분리할 수 있는지
