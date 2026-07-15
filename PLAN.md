# PLAN.md — 사전 등록 실험 설계 (v2, 2026-07-13)

이 문서는 본실험(Phase 2) 시작 전에 고정된다. 시작 후에는 arm 코드(`src/arms/arms.py`)와
이 문서의 가설·metric·검정을 수정하지 않는다. 문헌 근거는 `RESEARCH_BASELINES.md`.

## 가설

- **H1 (축 분리)**: 주관적·상충 objective 하에서, objective별 전담 critic은 융합된
  단일 evaluator보다 나은 결과물을 만든다. (FUSED → AXES)
- **H2 (debate)**: 축별 critic 간 상호 반박(cross-critique)은 독립 critic 취합보다
  나은 결과물을 만든다. (AXES → MAD)
  - 메커니즘 예측: 단일/독립 evaluator는 라운드가 깊어질수록 관대화(leniency drift)
    하며, 적대적 동료 비판이 이를 억제한다. (in-loop critic 점수 궤적 vs held-out
    judge 궤적의 간극으로 측정)
- **H3 (front 출력)**: 애매한 objective에서는 단일 결과물보다 Pareto front 제시가
  사용자에게 더 유용하다. (인간 선택 스터디, Phase 3)

## Arms (동결 대상)

| arm | 구조 | 격리하는 질문 |
|---|---|---|
| ZS | zero-shot 1회 | 바닥 앵커 |
| BON | budget 소진까지 다양성 샘플링 (T=0.9) | 루프 없는 샘플링으로 충분한가 |
| SELF | self-critique + revise 루프 | 외부 evaluator의 가치 (→FUSED) |
| FUSED | planner + generator + 융합 evaluator (Anthropic 하네스) | H1의 대조군 |
| AXES | 축별 독립 critic → moderator | H1 / H2의 대조군 |
| MAD | AXES + 반복 cross-critique 후 synthesis | H2 |

공통 규칙:
- **compute matching**: 태스크당 총 토큰(budget, prompt+completion, 모든 LLM/VLM 호출
  포함) 고정. 조기 종료 없음 — "good enough" 판정은 로깅만 하고 무시. 라운드 시작 전
  잔여 예산 < 직전 라운드 비용의 60%면 중단 (초과 방지).
- **후보 보존**: 모든 중간 산출물은 `tokens_at` 스탬프와 함께 후보로 저장
  (quality-vs-token 곡선은 사후 절단으로 계산).
- **공유 selector**: 최종 결과물 = 렌더 probe `func_objective` 최대(동률이면 최신).
  전 arm 동일, layer-A 신호만 사용.
- FUSED/AXES/MAD는 planner·generator·revision 코드를 공유하고 evaluator 블록만 다름.

## 축 (main4)

functionality(검증가능, Playwright probe evidence) + design / originality / craft
(주관, VLM 스크린샷 평가). Anthropic 하네스의 rubric과 일치. **efficiency 제외**
(퇴화 페이지 보상 문제, ver5/6 교훈). Ablation용: coarse2 / fine6.

## 태스크 (2026-07-14 개정: ArtifactsBench 단일 트랙)

- **ArtifactsBench** (Tencent, 1,825 queries) — 디자인 자유도 높은 카테고리
  (Game Dev / SVG / Web Apps / Simulations / Multimedia) `design_forward` 프리셋,
  medium+hard, **n=50**. + 자유도 낮은 대조(`low_freedom`) ~10개 (headroom 용량-반응).
  근거: CRUD류 층화는 기능 난이도만 올리고 주관 축 headroom을 줄임 — H1/H2의 전장은
  주관 축이므로 디자인 천장이 높은 태스크가 맞음. 단일 파일 아티팩트 = 기존 인프라 유지.
- WebGen-Bench 기능 anchor 트랙은 **제외** (사용자 결정 2026-07-14). 기능 붕괴 감시는
  probe func_objective(기술 통계) + 체크리스트의 기능 항목으로 대체.
- 생성기: **Qwen3.6-35B-A3B-FP8 단일** (사용자 결정 2026-07-14).
- critic VLM: **Qwen2.5-VL-32B — 생성기와 동급** (layer A 전용). debate 품질은 참가자
  지능에 bounded(2511.07784)이므로 7B critic은 H2를 confound함.

## 평가 (3층 격리)

- **층 A (최적화 신호, 증거 사용 금지)**: VL-32B critics(생성기 동급), Playwright probe, UIClip.
- **층 B (자동 스크리닝, held-out)**:
  1. *(absolute, 진단+곡선)* ArtifactsBench 체크리스트 채점 — 과제별 항목을 시계열
     스크린샷 3장(t0/t1/t2)으로 held-out judge가 pass/fail → fraction. 후보 전체에
     선형 비용이라 quality-vs-token·관대화 곡선의 점수원. 체크리스트는 층 B 자산 —
     critic에게 노출 금지.
  2. *(primary-subjective)* held-out judge의 강제선택 pairwise (양쪽 순서 각 1회,
     tie 불허) → Bradley-Terry. **이중 심판** (ArtifactsBench 프로토콜):
     기본 judge = Qwen2.5-VL-72B (오픈, self-host). Gemini-2.5-Pro는 키 확보 시
     추가(채점은 사후 작업이라 재생성 불필요; judge별 결과 파일 분리). 심판 간
     일치율 보고. 능력 사다리: critic 32B = 생성기급 < judge 72B < 인간.
  - **UIClip은 층 B에서 영구 제외** (층 A에서 사용하므로 — Goodhart).
  - 1–5 절대 점수(WebGen appearance 등)는 기술 통계로만 보고.
- **층 C (인간, 최종 증거; Phase 3)**: blind 강제선택 pairwise + BT.
  C1 = arm별 최종 결과물 품질 (H1/H2), C2 = front k개 vs BON k개 중 선택 →
  선택 만족도 (H3). judge-인간 일치율을 C 데이터 ~200쌍으로 측정·보고.

## 사전 등록된 비교와 검정

주요 비교 4개 (paired sign test, 태스크 단위 다수결, Holm-Bonferroni 보정):
1. SELF vs FUSED (외부 평가의 가치)
2. FUSED vs AXES (**H1**)
3. AXES vs MAD (**H2**)
4. BON vs MAD (전체 루프 vs 샘플링)

front 비교(HV)는 arm당 후보 k=4 균등 서브샘플(고정 seed)로 계산, 전체 후보 HV는
후보 수 공개와 함께 보조 지표.

## Ablation (부분집합 n=25, MAD/AXES 계열만)

- debate 깊이: 0(=AXES) / 1 / 3 — H2 용량-반응 (문헌 예측: flat)
- 축 개수: 1(=FUSED) / coarse2 / main4 / fine6 — H1 용량-반응
- 관대화: 라운드별 critic 점수 vs held-out judge 점수의 간극, AXES vs MAD 기울기 비교

## 분별력 게이트 (Phase 1 → 2 진입 조건)

n=10 파일럿에서 다음 중 하나면 **본실험 진입 금지**, 태스크 난이도/생성 범위 상향 후
재파일럿:
- (a) held-out pairwise winrate가 전 쌍에서 45–55%에 갇힘
- (b) probe func_objective가 arm 무관 천장(>0.95)/바닥(<0.05)

## 실행 단계

1. **Phase 0**: 구조 개편 + mock smoke — 완료 (2026-07-13)
2. **Phase 1**: n=10 × 6 arms × Qwen3.6 파일럿 (ArtifactsBench design_forward) —
   budget 캘리브레이션(arm당 평균 토큰 편차 <10%), judge 점검, 분별력 게이트
3. **Phase 2**: (50+10 대조) × 6 arms + ablation grid + 층 B 채점
4. **Phase 3**: 층 C human study (층 B로 스토리 확인 후 설계)

## 이 설계가 성립시키는 결론

- MAD가 BON·AXES를 동시에 이기고 관대화 간극 감소 관측 → "주관적·상충 objective에서
  debate가 작동하며 메커니즘은 관대화 억제" (본 주장)
- AXES까지만 이기고 MAD 무효 → "축 분리가 전부" (정직한 대안 결론, 그 자체로 기여)
- BON이 전부 이김 → 압축된 결론: 이 도메인에서도 샘플링이 왕 (부정 결과 보고)
