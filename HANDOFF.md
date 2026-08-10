# 인수인계 (MAD 웹디자인 실험) — 2026-07-27

너는 이 작업을 이어받는 Claude다. 아래를 읽고 현 상태에서 계속하라.
프로젝트 루트: `/home2/sunghyunchoi/multi_obj` (모든 경로는 여기 기준).
사전등록 문서 = `PLAN.md` (늘 최신 진실). 자동메모리에 `mad-webdesign-experiment`,
`gsai-cluster-quirks` 있음(참고).

---

## 0. 한 줄 요약
Multi-Agent Debate(MAD)가 **주관적·상충 objective(웹 디자인)** 에서 더 좋은 단일
결과물을 내는지 검증. 지금 **치명적 critic 파서 버그를 고쳐 cap-10을 재실행 중**이고,
**gold(Opus 크리틱) 실험은 이미 검증 완료(견고)**.

## 1. 실험 arm 구조 (매 라운드 "평가 방식"만 다름, 나머지 동일)
공유 r0에서 시작 → 최대 10라운드, 평가→revision지시→`gen_revision(instr, 이전HTML,
지시)`→새 후보. 평가자가 good_enough 선언 시 정지(그 후보가 최종, 외부 selector 없음).
- **SELF** (`run_self`): 외부 크리틱 없음. `gen_self_refine` 한 호출이 자기 HTML 보고
  비평+수정 동시. (외부피드백 격리 바닥선)
- **FUSED** (`run_fused`): 통합 크리틱 1명(`fused_critic`)이 전 기준 통째로 → 제안 1개.
  (Anthropic 하네스 루프)
- **AXES** (`run_axes`→`_critic_loop(use_debate=False)`): 축별 4명(func/design/orig/
  craft) 독립 비평 → moderator(`synthesize`)가 취합. (H1: 분해)
- **MAD** (`run_mad`→`_critic_loop(use_debate=True)`): AXES + `cross_critique`(서로 반박
  =토론) → synthesize. (H2: 토론)
코드: `src/arms/arms.py`, `src/critics/{critics.py,debate.py,prompts.py}`, `src/config.py`(축 정의).

## 2. ★치명 버그와 수정 (가장 중요 — 이것 때문에 재실행)
**증상**: cap-10의 AXES/MAD 축별 크리틱이 **86%가 `(no parse)`** 였음. →산출물 기반
debate 신호 유실 → "MAD/AXES가 debate로 이겼다" 해석에 구멍(confound).
**근본원인**: `src/infra/client.py`의 `generate_vlm()`(크리틱은 이미지를 봐서 이 경로)가
`max_tokens=1024`뿐 → Qwen3.6 thinking 프리앰블이 예산을 다 먹어 **JSON이 잘림**. (thinking
자체가 아니라 토큰부족이 원인)
**수정(완료, 커밋 안 함/로컬)**:
1. 크리틱 `max_tokens` 1024→**4096** (`critics.py`, `debate.py`) + **thinking ON 유지**
   (크리틱은 추론작업이라 켜두는 게 품질↑). gen 경로는 thinking OFF 유지(클린 HTML).
2. `src/infra/parse.py` `extract_json` 관대화: `<think>`제거·다중후보·정규식폴백(`_lenient`).
3. `critics.py`: 파싱 실패 시 **thinking off로 1회 재시도**(짧은 JSON 보장), 그래도 실패면
   **salvage**(잘린 추론 프로즈를 critique로 사용) → `(no parse)` 거의 0. 실패 시 raw 300자 저장.
4. `client.py`에 `think` 토글 추가(generate/generate_vlm).
**검증**: 재실행 preflight 파싱 3/3 OK, **FUSED suggestion 10%→93%**.

## 3. 데이터 디렉토리 (3개 실험)
- `results/strongen/` = **1라운드**, gold vs weak. r0 공유(`r0_pool/s0`), weak 4arm
  (`s0/{SELF,FUSED,AXES,MAD}`), gold 3구조(`gold/{task}/r1_{goldfused,goldaxes,goldmad}`).
  gold 크리틱 = **내가(Opus) 산출물 보고 직접 작성**(`_critiques_gold*`), MAD는 진짜 4자토론
  전사(`_debate_goldmad`). ★gold는 파서버그 무관·깨끗.
- `results/strongenall/` = **cap-10**(파서버그 있는 옛 버전). SELF/FUSED/AXES/MAD.
- `results/strongenall2/` = **cap-10 재실행(파서 수정본)** ← 지금 생성 중.

## 4. 평가 방법 (judge=Fable, 블라인드)
- judge = **Fable**(`claude-fable-5`, Agent tool `model:"fable"`), 크리틱 쓴 Opus와 다른
  모델. **각 태스크가 격리 세션**.
- **완전 블라인드**: 8변형을 익명코드 A~H로 셔플, 파일경로도 중립복사
  (`report/blind/{task}/{code}_{frame}.png`), 매핑은 `blind_key.json`(judge 미노출).
  `blind_manifest.json` 사용. 채점 후 `tools/blind_unmap.py`로 복원.
- **rubric = ArtifactsBench 원문 방식 채택**(인간 94.4% 검증): GitHub Tencent-Hunyuan/
  ArtifactsBenchmark. 프롬프트=엄격 코드리뷰 전문가 페르소나 + per-task 체크리스트 +
  단일 Overall. 우리는 그 프롬프트 구조에 **우리 4축을 0/3/5/8/10 앵커 항목**으로 넣어
  Fable에 배치-블라인드 채점(`report/checklist_4axis.json`). 결과 파일
  `report/ab_blind_scores_{task}.json`(코드별 4축+overall+**reason**).

## 5. 현재 확정 결과 (strongen, AB rubric 블라인드, ÷4=0-10)
gold_axes **5.27** > gold_fused 4.75 > gold_mad 4.44 > weak_self 4.42 > weak_fused 4.38
> weak_axes 4.25 > weak_mad 4.23 > r0 3.92. **gold 3종 top-3 싹쓸이, best-gold>best-weak
9/12**. 두 rubric(내 요약/ArtifactsBench앵커) 모두 동일 결론 → "좋은 크리틱(gold)이 결과를
올린다"는 **견고**. (단 weak는 파서버그 산출물 채점이라, cap-10 재실행 후 strongen weak도
재생성·재채점해 정합시키는 게 이상적)
- 현재 `results/strongen/report/scores_{task}.json` = **8변형 전부 AB점수+reason** 반영됨.
  이전 블라인드(요약rubric)는 `report/scores_backup_blindsummary/`에 백업.

## 6. 지금 돌아가는 것 / 다음 할 일
- **job 665218 `capfix` (RUNNING, n87)** → `results/strongenall2`. SELF✅ FUSED✅(12/12),
  AXES 진행, MAD 남음. 스크립트 `cluster/run_capfix.sh`(preflight+끝에 파싱률 자동출력).
  모니터 background id `bjnofdkit`.
- **끝나면 순서대로**:
  1. 파싱률 확인: strongenall2의 AXES/MAD `debate.critiques` `(no parse)` 비율 (옛 86%→?).
     낮아졌으면 성공.
  2. **블라인드 재채점**: strongenall2 최종본을 위 4·5의 방식(ArtifactsBench 앵커 rubric,
     Fable, 코드 A~E 익명셔플)으로. cap-10은 5arm(r0,SELF,FUSED,AXES,MAD). 스테이징·unmap은
     `tools/blind_unmap.py`/기존 blind_manifest 패턴 참고.
  3. **cap-10 표 B(라운드별 궤적)** 재산출 원하면 라운드별 블라인드 채점(전에 하던 방식:
     `report/traj/` 익명 셀, 라운드 셔플). 비싸니 사용자 확인 후.
  4. **strongen weak 재생성/재채점**(선택): 수정된 크리틱으로 weak 1라운드 다시 → gold vs
     weak 완전 정합.
  5. 통합 리포트 갱신: `tools/make_combined_report.py`(3탭: strongen/cap최종/cap궤적,
     이미지클릭→라이트박스+의견). 산출물 `results/strongenall/report/combined_report.html`.

## 7. 주요 스크립트
- `tools/make_combined_report.py` 통합리포트(탭①=strongen AB점수+reason, 클릭시 의견).
- `tools/blind_unmap.py` 코드→variant 복원+집계.
- `tools/strongen_gold.py` gold r1 생성(`--only`로 특정만). `GEN_CONTEXT_LIMIT=49152` 필수.
- `cluster/run_capfix.sh` cap-10 재실행. `cluster/run_strongenall.sh` 원본 cap-10.
- gold 4자토론 워크플로우: `.claude/.../workflows/scripts/gold-debate-wf_*.js`(참고).

## 8. GSAI 클러스터 함정 (필독, 메모리에도 있음)
- 로그인노드만 인터넷(다운로드는 거기서). compute노드 egress 없음.
- sbatch cwd는 `${SLURM_SUBMIT_DIR}` 써야 함(spool dir 문제).
- 공유노드 → **유니크 포트 + 서버 identity 확인**(`grep Qwen3.6-35B-A3B`) 필수(포트레이스).
- **held allocation 절대 replacement RUNNING 전에 취소 금지**(자리 뺏김). H200 자주 만석.
- QOS `hpgpu`, 파티션 `H200,H200-ZT,H200-PCIe-ZT`.
- 모델 = `Qwen/Qwen3.6-35B-A3B`(MoE, thinking 모델, vLLM 0.25.1 지원). judge=Fable(Agent).
- 세션 리밋 9pm Asia/Seoul 리셋.

## 9. 방법론 원칙 (사용자가 강하게 요구한 것들)
- **모든 채점은 블라인드**(라벨·경로·순서 다 익명). 라벨 새면 다시 함.
- gold 크리틱은 **산출물을 실제로 보고**(Opus가 이미지 읽음) 작성. MAD gold는 진짜 4자토론.
- 문제 터지면 **바로 고치고 확실히 돌 때까지 확인**. 잡은 자리 안 나면 대기 걸어둠.
- 토큰 비용 민감 — 큰 fan-out(수십 에이전트) 전엔 확인.
