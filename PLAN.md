# PLAN.md — 사전 등록 실험 설계 (v2, 2026-07-13 / 개정 2026-07-15)

이 문서는 본실험(Phase 2) 시작 전에 고정된다. 시작 후에는 arm 코드(`src/arms/arms.py`)와
이 문서의 가설·metric·검정을 수정하지 않는다. 문헌 근거는 `RESEARCH_BASELINES.md`.

**주장의 단위 (2026-07-15 스코프 확정)**: 이 실험이 검증하는 것은 *단일 최종 결과물의
품질*이다 — "정량화하기 어려운(주관적)·상충하는 objective들의 MOO 태스크에서, 축별
전담 agent 간 debate(MAD)가 더 좋은 결과물을 만든다." Pareto front를 *출력*하는 것
(구 H3)은 arm이 population을 유지해야 성립하므로 v3로 이연 (`_archive/pareto_deferred.py`).

## 가설

- **H1 (축 분리)**: 주관적·상충 objective 하에서, objective별 전담 critic은 융합된
  단일 evaluator보다 나은 결과물을 만든다. (FUSED → AXES)
- **H2 (debate)**: 축별 critic 간 상호 반박(cross-critique)은 독립 critic 취합보다
  나은 결과물을 만든다. (AXES → MAD)
  - 메커니즘 예측: 단일/독립 evaluator는 라운드가 깊어질수록 관대화(leniency drift)
    하며, 적대적 동료 비판이 이를 억제한다. (in-loop critic 점수 궤적 vs held-out
    judge 궤적의 간극으로 측정)
- ~~H3 (front 출력)~~ — **v3로 이연** (위 스코프 확정 참조).
- **2차 예측 (균질화 signature, 2601.08003 근거)**: moderator의 강제 합의가
  창의적 다양성을 깎는다면 MAD는 design/craft에서 이기고 **originality 축에서만**
  약한 패턴이 나온다 (축별 절대 점수로 무비용 측정). 관측되면 v3(합의 대신
  상충 방향 분기 + front 보존)의 직접 동기가 된다.

## Arms (동결 대상; 2026-07-15 사용자 결정으로 5개)

| arm | 구조 | 격리하는 질문 |
|---|---|---|
| ZS | zero-shot 1회 | 바닥 앵커 |
| SELF | self-critique + revise 루프 | 외부 evaluator의 가치 (→FUSED) |
| FUSED | planner + generator + 융합 evaluator (Anthropic 하네스) | H1의 대조군 |
| AXES | 축별 전문가 critic (독립) → moderator | H1 / H2의 대조군 |
| MAD | AXES + cross-critique 후 synthesis | **H2 (주 가설)** |

제외: ~~BON~~ (다양성 샘플링 베이스라인) — 코드는 유지, 실행 목록에서만 제외.
필요 시(리뷰 대응 등) 같은 태스크에 사후 추가 가능.

**본실험 직전 개정 (v3, 2026-07-15 밤 — 파일럿 발견 반영, main60 시작 전 확정)**:
- **라운드 캡 4→15→8** (2단 개정): 블로그의 "이득은 ~10회차" 관측 검증차 15로
  올렸으나, deep15 ablation(15태스크, 전 후보 채점)의 quality-vs-round 곡선이
  AXES/MAD는 r4-8 피크 후 퇴화함을 보임(MAD 피크 6.95@r4 → 6.37@r15) →
  본실험 시작 전 캡 8로 확정 (피크 구간 포함, 퇴화 구간 배제, axisabl과 정합).
  FUSED는 완만한 상승 지속(블로그 관측은 융합 평가자에만 부분 성립) — 곡선
  자체가 부록 그림. 평가자 만족 선언은 45태스크×15라운드에서 0회(SELF 제외)
  → "패널은 정지를 스스로 못 한다"가 확정 관측.
- **모든 정지 신호를 명시적 good_enough 선언으로 통일**: SELF는 GOOD_ENOUGH 출력
  (기존: 정지 수단 없음), FUSED는 JSON good_enough bool(기존: 점수 4+ 임계값),
  AXES/MAD는 기존대로 moderator. 점수는 관대화 분석용 기록만.
- **오프라인 샌드박스 규칙을 생성 프롬프트에 명시** (파일럿 빈 화면 근본 원인:
  CDN 의존 생성 + 차단 → 빈 화면/로딩 고착). functionality critic에 페이지 에러
  원문 전달, checklist judge에 빈 화면 전항목 fail 가드.
- **기계적 listwise 제외 규칙** (tools/find_broken_finals.py): 어떤 arm이든 final이
  3샷 전부 픽셀 std<3 이거나 judge overall==0이면 그 태스크를 모든 표에서 제외.
  파일럿 소급 검증: 수동 판정과 100% 일치.
- **태스크 재큐레이션 v3**: 오염 7개 추가 발견·교체 (258 Mapbox, 404 HarmonyOS,
  469 URL분석, 292 ArkTS, 658 URL스크린샷, 1716 스크래핑, 360 Eclipse[교체 중 발견]).
  최종 60개 유니크, red-flag 0. 백업: main_task_ids.v2_backup.txt.

**Shared-r0 paired design (2026-07-16 추가, ablation `sharedr0`)**: deep15에서
초기 생성 추첨이 arm 순위를 교란함을 확인 (MAD-AXES r0 격차 -0.95는 동일 코드
경로의 순수 샘플링; sign p=0.109; probe 기준 3개 런에서 체계적 차이 없음).
초기 생성은 검증 대상이 아니므로 태스크×시드마다 planner spec + r0를 1회 생성해
4개 루프 arm이 공유 (common random numbers 방식). 15태스크 × 시드3 × 캡10,
전 후보 채점. SELF도 동일 r0 상속(정의가 "주어진 시작점에서 자기비평 루프"로
이동함을 명시). 본실험(main60)은 사전등록대로 fresh-r0 유지 — sharedr0는
확증용 paired 재현.

공통 규칙 (실행 체제 확정 v2, 2026-07-15 — **consensus-stop, 배포 semantics**):
- **합의 시 즉시 정지, 그 결과물이 최종**: 각 arm은 자기 evaluator가 "충분하다"고
  선언하는 순간 멈추고(FUSED: 점수 4+/제안 없음, AXES/MAD: moderator 합의),
  **그 시점의 결과물이 최종 출력**이다. 외부 selector 없음 — inference 시 쓸 수
  없는 하네스측 선택기는 방법이 아니라 하네스를 측정하게 되므로 배제.
  이래야 "스스로 좋다고 판단하는 능력"까지 포함해 debate의 의미가 측정된다.
- **하드 캡 4라운드**: 합의가 안 나면 4라운드에서 강제 정지, r4 결과물이 최종.
  SELF는 정지 신호가 없는 방법이므로 수정 4회 후 최종, ZS는 1회 생성.
- **토큰은 보고만**: arm별 비용 표로 기술 보고(매칭·중단 기준 아님). budget은
  폭주 방지 가드(250k).
- **후보 보존**: 모든 중간 산출물 저장 — 체크리스트 곡선·관대화 분석용.
  관대화 궤적은 각 arm의 정지 시점까지 관측된다(consensus-stop의 대가로 궤적이
  절단될 수 있음을 명시; 정지 라운드 분포 자체도 보고 지표).
- probe(func_objective)는 선택에 사용하지 않음 — 기술 통계로만 보고.
- FUSED/AXES/MAD는 planner·generator·revision 코드를 공유하고 evaluator 블록만 다름.

## 축 (main4)

functionality(검증가능, Playwright probe evidence) + design / originality / craft
(주관, VLM 스크린샷 평가). Anthropic 하네스의 rubric과 일치. **efficiency 제외**
(퇴화 페이지 보상 문제, ver5/6 교훈). Ablation용: coarse2 / fine6.

## 태스크 (2026-07-14 개정: ArtifactsBench 단일 트랙)

- **ArtifactsBench** (Tencent, 1,825 queries) — 디자인 자유도 높은 카테고리
  (Game Dev / SVG / Web Apps / Simulations / Multimedia) `design_forward` 프리셋,
  medium+hard, **n=50**. + 자유도 낮은 대조(`low_freedom`) ~10개 (headroom 용량-반응).
- **태스크 큐레이션 (2026-07-15, 실행 전)**: 최초 60개 중 12개가 특정 스택
  (Vue/React/Flask/Java/Android/Eclipse 등)을 요구해 "외부 요청 금지 단일 HTML"
  전제에서 충족 불가능 → 같은 class·difficulty의 클린 태스크로 교체 (regex
  레드플래그 필터, 최소 index 결정론적 선택). 중복 id 1개(7)도 발견·대체.
  최종 60개 유니크, 레드플래그 0. 이력: git `main_task_ids.txt`.
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
  **평가 방식 확정 (사용자 결정 2026-07-15): 절대 채점 (ArtifactsBench 방식).
  pairwise/BT는 하지 않는다** — 모든 결과물이 보존되므로, 절대 점수가 arm을
  분별하지 못하면(게이트 참조) 그때 pairwise를 사후 추가한다 (재생성 불필요;
  `judge_pair` 코드 보존).
  1. *(primary)* **절대 점수 (2026-07-15 확정)** — held-out judge가 결과물
     하나(시계열 스크린샷 3장)를 보고 **harness 블로그의 4개 기준
     (functionality / design / originality / craft, 블로그 원문 정의 그대로)**을
     각각 0-10점 채점, arm×태스크당 1회 호출(선형 비용).
     **주 지표 `overall` = 이 4개 점수의 단순 평균 (계산값, judge가 직접 매기지
     않음)** — 모든 사전등록 검정은 이 숫자로만. 4개 축 점수는 진단 부록
     (H1/H2 축별 해석 + 균질화 2차 예측용, 헤드라인 아님).
     집계 방식은 ArtifactsBench와 동형(차원별 채점→평균; 그 방식의 순위가 인간
     순위와 94.4% 일치), 기준 정의는 harness 블로그 — critic·debate·평가가
     같은 4개 기준을 공유해 최적화 목표와 평가 구인이 1:1.
  2. *(진단+곡선)* **체크리스트 채점** — ArtifactsBench 원 프로토콜 그대로
     (태스크별 항목 pass/fail → fraction). 후보 전체에 채점해
     quality-vs-round·관대화 곡선의 점수원. 체크리스트는 층 B 자산 —
     critic에게 노출 금지.
  - **이중 심판**: 기본 judge = Qwen2.5-VL-72B (오픈, self-host). Gemini-2.5-Pro는
     키 확보 시 추가(채점은 사후 작업이라 재생성 불필요; judge별 결과 파일 분리).
     심판 간 일치율 보고. 능력 사다리: critic 32B = 생성기급 < judge 72B < 인간.
  - **UIClip은 층 B에서 영구 제외** (층 A에서 사용하므로 — Goodhart).
  - 1–5 절대 점수(WebGen appearance 등)는 기술 통계로만 보고.
- **층 C (인간, 최종 증거; Phase 3)**: blind 강제선택 pairwise + BT.
  arm별 최종 결과물 품질 (H1/H2). judge-인간 일치율을 C 데이터 ~200쌍으로 측정·보고.

## 사전 등록된 비교와 검정

주요 비교 3개 (태스크 단위 paired sign test — 태스크별 두 arm의 절대 점수
`overall`을 비교, 동점 제외, Holm-Bonferroni 보정):
1. SELF vs FUSED (외부 평가의 가치)
2. FUSED vs AXES (**H1**)
3. AXES vs MAD (**H2**)
(BON 제외로 "루프 vs 샘플링" 비교는 사전등록에서 제거; 필요 시 사후 추가)

## Ablation (부분집합 n=25, MAD/AXES 계열만)

- debate 깊이: 0(=AXES) / 1 / 3 — H2 용량-반응 (문헌 예측: flat)
- 축 개수: 1(=FUSED) / coarse2 / main4 / fine6 — H1 용량-반응
- 관대화: 라운드별 critic 점수 vs held-out judge 점수의 간극, AXES vs MAD 기울기 비교

## 분별력 게이트 (Phase 1 → 2 진입 조건)

n=10 파일럿에서 다음 중 하나면 **본실험 진입 금지**, 태스크 난이도/생성 범위 상향 후
재파일럿:
- (a) 사전등록 비교 전부에서 태스크 단위 점수 우열 split이 45–55%에 갇히거나
  동점 비율이 과반 (절대 척도가 arm을 분별 못 함 → pairwise 사후 추가 검토)
- (b) probe func_objective가 arm 무관 천장(>0.95)/바닥(<0.05)

## 실행 단계

1. **Phase 0**: 구조 개편 + mock smoke — 완료 (2026-07-13)
2. **Phase 1**: n=10 × 5 arms × Qwen3.6 파일럿 (ArtifactsBench design_forward) —
   budget 캘리브레이션(arm당 평균 토큰 편차 <10%), judge 점검, 분별력 게이트
3. **Phase 2**: (50+10 대조) × 5 arms + ablation grid + 층 B 채점
4. **Phase 3**: 층 C human study (층 B로 스토리 확인 후 설계)

## 이 설계가 성립시키는 결론

- MAD가 AXES·FUSED를 이기고 관대화 간극 감소 관측 → "주관적·상충 objective에서
  debate가 작동하며 메커니즘은 관대화 억제" (본 주장)
- AXES까지만 이기고 MAD 무효 → "축 분리가 전부" (정직한 대안 결론, 그 자체로 기여)
- FUSED가 최강 → 부정 결과 보고: 축 분리·debate 모두 융합 evaluator를 못 이김
