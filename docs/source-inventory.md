# Source Inventory

## 기준선

- 원본 루트: 로컬의 `Learn Harness Engineering` 읽기 전용 미러
- 라이브 재검증: `HARNESS_ENGINEERING_SOURCE_ROOT`에 로컬 원본 루트를 지정
- 취급 방식: 읽기 전용
- 인벤토리 날짜: 2026-07-25
- 재귀 엔트리: 87개
- 디렉터리: 22개
- 파일: 65개
- 총 파일 크기: 287,986바이트
- 형식: `.md` 60, `.txt` 3, `.json` 1, `.sh` 1
- 읽기 결과: 65/65 UTF-8 성공, 총 3,683줄
- 빈 파일·심볼릭 링크·기타 파일: 없음

## 누락 방지 절차

1. 숨김 항목을 포함해 루트 아래를 재귀 순회했습니다.
2. 일반 파일과 디렉터리, 심볼릭 링크를 구분했습니다.
3. 모든 일반 파일을 UTF-8 원문으로 읽었습니다.
4. 크기와 SHA-256을 계산하고 동일 해시를 비교했습니다.
5. Obsidian 위키링크, 임베드, Markdown 링크, 이미지 링크를 별도로 파싱했습니다.
6. 모든 파일을 강의·템플릿·참고·고급 팩·SOP·스킬·실습으로 분류해
   내용과 적용 가능성을 분석했습니다.

## 형식·링크·중복 감사

- 동일 SHA-256 파일: 0쌍
- 의미상 반복: 실습 6개가 같은 교육용 골격을 공유하지만 목표와 하네스
  메커니즘이 달라 중복 제거 대상이 아닙니다.
- Obsidian 위키링크: 39개, 39개 모두 현재 원본 트리의 파일로 해석 가능
- Markdown 링크: 111개(외부 85, 로컬 26)
- 임베드 `![[...]]`: 0개
- Markdown 이미지: 0개
- 바이너리 첨부: 0개
- 코드 펜스: 44개
- `CHAPTER 04` 코드 예시 안의 `docs/api-patterns.md`,
  `docs/database-rules.md`, `docs/testing-standards.md`는 예시 프로젝트 경로이며
  원본 학습 트리의 누락 링크가 아닙니다.

## 전체 파일 원장

`SHA-256`은 앞 12자를 표시합니다. 모든 행은 이번 단계에서 원문 읽기와
분석을 완료했습니다.

| Source ID | 경로 | Bytes | SHA-256 | 핵심 역할 |
| --- | --- | ---: | --- | --- |
| SRC-IDX-001 | `_index.md` | 3,261 | `b7f0096ff3b8` | 강의·실습·리소스 진입점, 출처·MIT·닫힌 루프 |
| SRC-CH-001 | `CHAPTER 01. 강력한 모델도 실행 신뢰성을 보장하지 않는다.md` | 16,552 | `9dbdbbcf6b4c` | 모델보다 하네스, 5개 실패 레이어, 진단 루프 |
| SRC-CH-002 | `CHAPTER 02. 하네스란 실제로 무엇인가.md` | 13,422 | `af0e8227d138` | 지시·도구·환경·상태·피드백 5개 하위 시스템 |
| SRC-CH-003 | `CHAPTER 03. 저장소를 단일 진실 원천으로 만들어라.md` | 15,203 | `820b4233d3f6` | SoR, 콜드 스타트 질문, 지식 근접성·ACID |
| SRC-CH-004 | `CHAPTER 04. 명령 파일을 여러 파일로 분산하라.md` | 15,013 | `5fc1863729ef` | 짧은 라우터, 점진적 공개, 지침 SNR·수명주기 |
| SRC-CH-005 | `CHAPTER 05. 세션을 넘어 컨텍스트를 살아있게 유지하라.md` | 17,917 | `189aaba7a56a` | 진행·결정·검증·Git 체크포인트, 재구축 비용 |
| SRC-CH-006 | `CHAPTER 06. 모든 에이전트 세션 전에 초기화하라.md` | 16,101 | `b4f1e07f692d` | 전용 초기화, 부트스트랩 계약, 웜 스타트 |
| SRC-CH-007 | `CHAPTER 07. 에이전트에게 명확한 작업 경계를 그어 주어야 합니다.md` | 13,454 | `31ebb7c51e08` | WIP=1, 완료 압력, 검증 완료율 |
| SRC-CH-008 | `CHAPTER 08. 기능 목록으로 에이전트의 행동을 제약하십시오.md` | 12,851 | `208ca9068b01` | 기능 삼중 구조, 상태 기계, 증거 게이트 |
| SRC-CH-009 | `CHAPTER 09. 에이전트가 너무 일찍 완료를 선언하지 못하도록 방지하기.md` | 16,720 | `6ab3631ace27` | 외부화된 종료 판단, 3단계 게이트, 역할 분리 |
| SRC-CH-010 | `CHAPTER 10. 엔드투엔드 테스트(end-to-end testing)만이 진정한 검증이다.md` | 16,992 | `ca34a87620e5` | 경계 결함, E2E, 실행 가능한 아키텍처 규칙 |
| SRC-CH-011 | `CHAPTER 11. 에이전트의 런타임을 관측 가능하게 만들어라.md` | 12,727 | `55344dc6f937` | 런타임·프로세스 관측, 계약·루브릭·트레이스 |
| SRC-CH-012 | `CHAPTER 12. 모든 세션은 클린 상태(clean state)로 끝나야 한다.md` | 13,512 | `c9df5914da66` | 5차원 클린 상태, 품질 문서, 절제·멱등 정리 |
| SRC-RES-001 | `리소스/index.md` | 2,831 | `610c2fe83d9f` | 최소 4파일 팩과 고급 팩의 도입 기준 |
| SRC-TPL-001 | `리소스/templates/AGENTS.md` | 2,953 | `6137f95fbd6b` | Codex용 시작·작업·완료·종료 템플릿 |
| SRC-TPL-002 | `리소스/templates/CLAUDE.md` | 2,367 | `12bc92bf3f7f` | Claude용 동등 진입점 |
| SRC-TPL-003 | `리소스/templates/claude-progress.md` | 1,363 | `8bdac01ed6fb` | 세션별 진행·증거·다음 행동 |
| SRC-TPL-004 | `리소스/templates/clean-state-checklist.md` | 795 | `395ac217d0c3` | 재시작 가능성·미검증 작업 종료 점검 |
| SRC-TPL-005 | `리소스/templates/evaluator-rubric.md` | 1,265 | `de07f017c118` | 정확성·범위·신뢰성·인계 평가 |
| SRC-TPL-006 | `리소스/templates/feature_list.json` | 2,007 | `a4e429ab96cd` | WIP·상태·검증·증거의 기계 원장 |
| SRC-TPL-007 | `리소스/templates/index.md` | 11,810 | `a38d13b78e32` | 템플릿별 사용법·보정·품질 추적 |
| SRC-TPL-008 | `리소스/templates/init.sh` | 664 | `4f751620a48e` | 설치·기준 검증·시작 진입점 |
| SRC-TPL-009 | `리소스/templates/quality-document.md` | 2,227 | `e0601b6c9ba8` | 도메인·계층 품질 스냅샷과 추세 |
| SRC-TPL-010 | `리소스/templates/session-handoff.md` | 982 | `d530525efec6` | 검증·변경·미검증·다음 행동의 인계 |
| SRC-REF-001 | `리소스/reference/coding-agent-startup-flow.md` | 1,783 | `e6f0d0ac6072` | 고정 시작 순서와 종료 미러 |
| SRC-REF-002 | `리소스/reference/glossary.md` | 9,749 | `47c93644a198` | 용어·토큰·경로 표기 단일 진실 |
| SRC-REF-003 | `리소스/reference/index.md` | 1,243 | `3df0f43df71c` | 참고 문서 라우터와 읽기 순서 |
| SRC-REF-004 | `리소스/reference/initializer-agent-playbook.md` | 1,717 | `7e0d007f99ee` | 초기화 필수 산출물·성공 테스트 |
| SRC-REF-005 | `리소스/reference/method-map.md` | 2,107 | `e8b3fdc69ce9` | 실패 유형에서 최소 수정 산출물로의 맵 |
| SRC-REF-006 | `리소스/reference/prompt-calibration.md` | 1,215 | `090fa8851643` | 루트에 남길 것과 분리할 것 |
| SRC-ADV-001 | `리소스/openai-advanced/index.md` | 3,421 | `74bd00dd9826` | 최소 팩에서 고급 팩으로의 승격 기준 |
| SRC-ADV-002 | `리소스/openai-advanced/repo-template/index.md` | 1,408 | `55acd098df90` | 고급 저장소 복사·적용 순서 |
| SRC-ADV-003 | `리소스/openai-advanced/repo-template/AGENTS.md` | 3,250 | `a542735aa5a6` | 고급 라우터·작업 계약·세션 종료 |
| SRC-ADV-004 | `리소스/openai-advanced/repo-template/ARCHITECTURE.md` | 2,894 | `6c797baf95d6` | 도메인·계층·횡단 관심사 지도 |
| SRC-ADV-005 | `리소스/openai-advanced/repo-template/docs/DESIGN.md` | 1,397 | `1c2bcdd433b2` | 설계 진입점과 결정 수명주기 |
| SRC-ADV-006 | `리소스/openai-advanced/repo-template/docs/FRONTEND.md` | 1,446 | `b854a4665c65` | UI 상태·접근성·런타임 검증 |
| SRC-ADV-007 | `리소스/openai-advanced/repo-template/docs/PLANS.md` | 1,690 | `a1b4de7606ca` | 활성·완료 계획과 기술 부채 수명주기 |
| SRC-ADV-008 | `리소스/openai-advanced/repo-template/docs/PRODUCT_SENSE.md` | 1,240 | `1e800639d671` | 횡단 제품 판단과 금지 패턴 |
| SRC-ADV-009 | `리소스/openai-advanced/repo-template/docs/QUALITY_SCORE.md` | 1,827 | `ec5ea55ff33a` | 품질 등급·벤치마크·절제 로그 |
| SRC-ADV-010 | `리소스/openai-advanced/repo-template/docs/RELIABILITY.md` | 1,604 | `abbe90263ee7` | 표준 경로·신호·황금 여정 |
| SRC-ADV-011 | `리소스/openai-advanced/repo-template/docs/SECURITY.md` | 1,540 | `9ca4e599550f` | 비밀·입력·외부 행동·의존성 경계 |
| SRC-ADV-012 | `리소스/openai-advanced/repo-template/docs/design-docs/core-beliefs.md` | 900 | `88d30eefbcbc` | 에이전트 우선 핵심 신념 |
| SRC-ADV-013 | `리소스/openai-advanced/repo-template/docs/design-docs/index.md` | 1,047 | `3d382af0ebfa` | 수락·제안·폐기 결정 색인 |
| SRC-ADV-014 | `리소스/openai-advanced/repo-template/docs/exec-plans/active/index.md` | 596 | `467a0970fb4d` | 재개 가능한 활성 계획 폴더 |
| SRC-ADV-015 | `리소스/openai-advanced/repo-template/docs/exec-plans/completed/index.md` | 549 | `b951aca54c2b` | 완료 계획을 내구성 이력으로 보존 |
| SRC-ADV-016 | `리소스/openai-advanced/repo-template/docs/exec-plans/tech-debt-tracker.md` | 741 | `e4b5e6e85df7` | 의도적으로 미룬 부채와 재검토 트리거 |
| SRC-ADV-017 | `리소스/openai-advanced/repo-template/docs/generated/db-schema.md` | 778 | `bc2d40ce8ada` | 생성 산출물 출처·재생성 규칙 |
| SRC-ADV-018 | `리소스/openai-advanced/repo-template/docs/product-specs/index.md` | 718 | `b78ec3d5d44a` | 사용자 동작 명세 색인 |
| SRC-ADV-019 | `리소스/openai-advanced/repo-template/docs/product-specs/new-user-onboarding.md` | 815 | `ffa7f19d412d` | 관찰 가능한 흐름·인수·실패 상태 예시 |
| SRC-ADV-020 | `리소스/openai-advanced/repo-template/docs/references/design-system-reference-llms.txt` | 276 | `f189f24b8845` | 모델 친화적 디자인 시스템 추출 |
| SRC-ADV-021 | `리소스/openai-advanced/repo-template/docs/references/nixpacks-llms.txt` | 238 | `75ae8fb5e121` | 빌드·런타임 외부 참조 추출 |
| SRC-ADV-022 | `리소스/openai-advanced/repo-template/docs/references/uv-llms.txt` | 251 | `720640eb48ca` | 패키지·환경 외부 참조 추출 |
| SRC-ADV-023 | `리소스/openai-advanced/sops/chrome-devtools-validation-loop.md` | 2,314 | `16090e45256c` | UI BEFORE/AFTER 실행 검증 루프 |
| SRC-ADV-024 | `리소스/openai-advanced/sops/encode-knowledge-into-repo.md` | 2,698 | `1f083f7a0b71` | 외부·암묵 지식을 적절한 저장소 산출물로 이동 |
| SRC-ADV-025 | `리소스/openai-advanced/sops/index.md` | 1,753 | `32ca3b3900a7` | SOP 선택·적용 라우터 |
| SRC-ADV-026 | `리소스/openai-advanced/sops/layered-domain-architecture.md` | 2,763 | `907d25411a1d` | 계층 모델을 문서와 검사로 강제 |
| SRC-ADV-027 | `리소스/openai-advanced/sops/observability-feedback-loop.md` | 2,560 | `2221bea43756` | 쿼리·추론·수정·재시작·재검증 루프 |
| SRC-SKL-001 | `스킬/index.md` | 3,425 | `0a6d2eba1c23` | 하네스 생성 스킬의 5개 영역·참고 패턴 |
| SRC-PRJ-001 | `프로젝트/index.md` | 2,092 | `b52835dd7063` | 6개 점진 실습의 전체 지도 |
| SRC-PRJ-002 | `프로젝트/project-01-baseline-vs-minimal-harness/index.md` | 2,112 | `62caa13c4656` | 프롬프트 단독 대 최소 팩 비교 |
| SRC-PRJ-003 | `프로젝트/project-02-agent-readable-workspace/index.md` | 1,664 | `032bad9200a9` | 저장소 가독성과 핸드오프 비교 |
| SRC-PRJ-004 | `프로젝트/project-03-multi-session-continuity/index.md` | 1,664 | `a74b42adbf6f` | 진행·핸드오프·멀티세션 비교 |
| SRC-PRJ-005 | `프로젝트/project-04-incremental-indexing/index.md` | 1,657 | `4d0dce5d3042` | 런타임 피드백·범위 제어 비교 |
| SRC-PRJ-006 | `프로젝트/project-05-grounded-qa-verification/index.md` | 1,654 | `057555f1eb11` | 생성자·평가자 역할 분리 비교 |
| SRC-PRJ-007 | `프로젝트/project-06-runtime-observability-and-debugging/index.md` | 2,201 | `76cf1bc3aa47` | 전체 하네스·정리·절제 캡스톤 |
