# Source Disposition

## 목적

이 문서는 `docs/source-inventory.md`의 65개 Source ID가 Lite Core에 어떻게
반영되었거나 보류되었는지 한 행씩 설명합니다. 원본 자료를 모두 Core 파일로
복제했다는 뜻이 아니라, 각 자료에 대해 채택·통합·승격·참고 결정을
명시했다는 뜻입니다.

## 처분 기준

- `core-direct`: 설치된 Core 구성 요소나 실행 계약의 직접 근거입니다.
- `merged`: 별도 파일을 늘리지 않고 반복되는 원칙을 기존 Core 계약에
  통합했습니다.
- `deferred`: 관찰된 트리거가 있을 때 Standard 또는 Advanced 프로필로
  승격합니다.
- `reference-only`: 탐색·용어·실습·예시 자료로 보존하며 그 자체를 Core
  동작으로 과장하지 않습니다.

혼합 자료는 주된 처분을 기록하고, 부분적으로 보류한 범위는 `이유`와
`연결 대상`에 명시합니다. `HC-*`는
`template/core/docs/harness/components.json`의 설치된 구성 요소이고,
`standard:*`, `advanced:*`, `fixture:*`는 후속 프로필 또는 검증 Fixture의
안정적인 논리 이름입니다. 이 표의 `연결 대상`은 해당 자료가 영향을 준
넓은 처분 대상입니다. 반대로 `components.json.sources`는 설치 구성 요소를
직접 정당화하는 더 좁은 근거 집합이며, 반드시 이 넓은 연결의 부분집합이어야
합니다.

## 65개 자료 결정표

| Source ID | 경로 | Disposition | 반영 원칙 | 연결 대상 | 이유 |
| --- | --- | --- | --- | --- | --- |
| SRC-IDX-001 | `_index.md` | core-direct | 출처·라이선스·닫힌 검증 루프를 발견 가능하게 유지 | HC-005, HC-011, HC-013, HC-016, HC-017 | 강의 진입점의 공통 계약은 출처 원장·Source 맵·라이선스·고지와 실행 검증의 직접 근거이며, 강의 목차 자체는 복제하지 않습니다. |
| SRC-CH-001 | `CHAPTER 01. 강력한 모델도 실행 신뢰성을 보장하지 않는다.md` | merged | 모델 자신감 대신 실패를 구조적으로 진단하고 실행 증거로 판단 | HC-005, HC-007 | 다섯 실패 레이어를 별도 문서로 복제하지 않고 감사·게이트·실패 진단에 통합합니다. |
| SRC-CH-002 | `CHAPTER 02. 하네스란 실제로 무엇인가.md` | core-direct | 지시·도구·환경·상태·피드백을 함께 검사하고 명령은 안전한 인자로 실행 | HC-002, HC-005, standard:security | 명령 설정과 실행기 계약의 직접 근거입니다. 별도 보안 정책은 `standard:security`로 승격합니다. |
| SRC-CH-003 | `CHAPTER 03. 저장소를 단일 진실 원천으로 만들어라.md` | core-direct | 저장소를 SoR로 삼고 새 세션이 다섯 콜드 스타트 질문에 답하게 함 | HC-001, HC-004, HC-006 | 라우터·현재 상태·아키텍처와 콜드 스타트 계약의 직접 근거입니다. |
| SRC-CH-004 | `CHAPTER 04. 명령 파일을 여러 파일로 분산하라.md` | core-direct | 루트 지침을 짧은 라우터로 유지하고 세부 규칙을 가까운 문서로 점진 공개 | HC-001, HC-009, HC-012 | AGENTS 라우터·얇은 Claude 포인터·구성 요소 원장의 직접 근거입니다. 예시 프로젝트 경로는 생성하지 않습니다. |
| SRC-CH-005 | `CHAPTER 05. 세션을 넘어 컨텍스트를 살아있게 유지하라.md` | core-direct | 기계 상태와 bounded human snapshot으로 세션 재구축 비용을 낮춤 | HC-003, HC-004, HC-014, HC-015, standard:plans | 기능 원장·현재 상태·버전 수명주기의 직접 근거입니다. 별도 계획 이력은 `standard:plans`로 보류합니다. |
| SRC-CH-006 | `CHAPTER 06. 모든 에이전트 세션 전에 초기화하라.md` | core-direct | 멱등 초기화와 POSIX·PowerShell의 반복 가능한 프리플라이트 제공 | HC-002, HC-005, HC-010, HC-018 | 설정·검사기와 두 운영체제 진입 래퍼의 직접 근거입니다. |
| SRC-CH-007 | `CHAPTER 07. 에이전트에게 명확한 작업 경계를 그어 주어야 합니다.md` | core-direct | 기본 WIP를 하나로 제한하고 완료 또는 명시적 차단 뒤 다음 작업 선택 | HC-003, HC-005 | 상태 전환과 WIP=1 검사의 직접 근거입니다. |
| SRC-CH-008 | `CHAPTER 08. 기능 목록으로 에이전트의 행동을 제약하십시오.md` | core-direct | 기능 목록을 범위·상태·검증·증거의 실행 가능한 계약으로 사용 | HC-003, HC-005 | 기능 스키마와 영수증 기반 상태 전환의 직접 근거입니다. `passing` 비가역성은 현재 진실을 위해 채택하지 않습니다. |
| SRC-CH-009 | `CHAPTER 09. 에이전트가 너무 일찍 완료를 선언하지 못하도록 방지하기.md` | core-direct | 완료 판단을 위험 기반 외부 게이트와 영수증으로 분리 | HC-005, HC-007, advanced:independent-evaluator | Core에는 단계 게이트를 직접 반영하고, 별도 평가자 역할은 고위험일 때만 승격합니다. |
| SRC-CH-010 | `CHAPTER 10. 엔드투엔드 테스트(end-to-end testing)만이 진정한 검증이다.md` | core-direct | 경계 변경에는 E2E를 요구하고 위험이 낮은 변경은 가장 강한 적정 증거를 선택 | HC-005, HC-006, HC-007, standard:e2e | V0~V4와 황금 여정 계약의 직접 근거입니다. 고정 계층 아키텍처는 강제하지 않습니다. |
| SRC-CH-011 | `CHAPTER 11. 에이전트의 런타임을 관측 가능하게 만들어라.md` | merged | 실행 결과와 프로세스 판단을 구조화하고 필요할 때 관측성을 점진 승격 | HC-005, HC-007, advanced:observability | Core에는 명령·영수증·실패 신호를 통합하고 메트릭·트레이스는 분산 흐름이 있을 때 보류합니다. |
| SRC-CH-012 | `CHAPTER 12. 모든 세션은 클린 상태(clean state)로 끝나야 한다.md` | core-direct | 검증·상태·임시 산출물·재시작성·다음 행동의 클린 종료 검사 | HC-004, HC-005, HC-014, advanced:quality-ablation | 클린 상태와 안전한 제거·롤백은 Core에서 직접 검사하고 품질 추세·절제 실험은 고급 프로필로 보류합니다. |
| SRC-RES-001 | `리소스/index.md` | core-direct | 최소 팩으로 시작하고 관찰된 필요에 따라 고급 팩으로 승격 | HC-008 | Core 채택 절차와 프로필 경계의 직접 근거입니다. |
| SRC-TPL-001 | `리소스/templates/AGENTS.md` | core-direct | 시작·작업·완료·종료를 라우팅하는 공통 에이전트 계약 | HC-001 | 설치된 AGENTS 라우터의 직접 템플릿 근거입니다. |
| SRC-TPL-002 | `리소스/templates/CLAUDE.md` | core-direct | Claude 진입점을 제공하되 공통 규칙은 중복하지 않음 | HC-009 | 드리프트를 줄이기 위해 원문 전체 대신 얇은 포인터로 보정해 채택합니다. |
| SRC-TPL-003 | `리소스/templates/claude-progress.md` | core-direct | 현재 진행·증거·다음 행동을 bounded snapshot에 남김 | HC-004 | 별도 진행 파일을 추가하지 않고 STATE에 통합해 상태 중복을 막습니다. |
| SRC-TPL-004 | `리소스/templates/clean-state-checklist.md` | core-direct | 종료 전에 검증·재시작성·미검증 작업·임시 파일을 점검 | HC-004, HC-005 | 클린 상태 감사와 STATE 일관성 검사의 직접 근거입니다. |
| SRC-TPL-005 | `리소스/templates/evaluator-rubric.md` | deferred | 정확성·범위·신뢰성·인계를 독립적으로 평가 | advanced:independent-evaluator | Lite는 고정 게이트만 설치하고 주관적·고위험 평가가 필요할 때 루브릭을 추가합니다. |
| SRC-TPL-006 | `리소스/templates/feature_list.json` | core-direct | WIP·상태·검증·증거를 기계 판독 가능한 원장으로 관리 | HC-003, HC-005 | 설치된 기능 목록과 상태 검사기의 직접 근거입니다. |
| SRC-TPL-007 | `리소스/templates/index.md` | merged | 템플릿별 적용법·보정·품질 추적을 채택 절차로 라우팅 | HC-003, HC-008, advanced:quality-ablation | 사용법은 ADOPTION과 기능 계약에 합치고 장기 품질 추세는 조건부로 보류합니다. |
| SRC-TPL-008 | `리소스/templates/init.sh` | core-direct | 설치·기준 검증·시작을 POSIX·PowerShell의 반복 가능한 진입점으로 제공 | HC-002, HC-010, HC-018 | 설치된 두 init 래퍼와 설정 명령의 직접 근거입니다. |
| SRC-TPL-009 | `리소스/templates/quality-document.md` | deferred | 도메인·계층 품질 스냅샷과 추세를 주기적으로 검토 | advanced:quality-ablation | 작은 저장소에 상시 유지 비용을 부과하지 않고 품질 드리프트가 관찰될 때 추가합니다. |
| SRC-TPL-010 | `리소스/templates/session-handoff.md` | core-direct | 검증·변경·미검증·다음 행동을 다음 세션에 인계 | HC-004 | 별도 핸드오프 파일 대신 현재 STATE에 통합해 하나의 인간용 상태면을 유지합니다. |
| SRC-REF-001 | `리소스/reference/coding-agent-startup-flow.md` | core-direct | 고정 시작 순서와 종료 미러를 운영체제별 표준 진입 경로로 유지 | HC-001, HC-005, HC-010, HC-018 | 라우터·감사와 POSIX·PowerShell init 흐름의 직접 근거입니다. |
| SRC-REF-002 | `리소스/reference/glossary.md` | reference-only | 하네스 용어·토큰·경로 표기를 해석하는 기준 제공 | HC-011, HC-013 | 용어집을 Core에 복제하지 않고 Source 맵에서 원본 역할과 경로를 독립적으로 발견하게 합니다. |
| SRC-REF-003 | `리소스/reference/index.md` | reference-only | 참고 문서의 읽기 순서와 선택 경로 제공 | HC-008, HC-011 | 원본 참고 트리의 탐색 라우터이므로 동작으로 과장하지 않고 채택·출처 문서에서 역할을 보존합니다. |
| SRC-REF-004 | `리소스/reference/initializer-agent-playbook.md` | core-direct | 초기 채택 산출물과 운영체제별 콜드 스타트 성공 조건을 검사 | HC-005, HC-008, HC-010, HC-018 | 설치·감사와 POSIX·PowerShell 초기화 Fixture의 직접 근거입니다. |
| SRC-REF-005 | `리소스/reference/method-map.md` | merged | 관찰된 실패 유형을 가장 작은 수정 산출물과 검사로 연결 | HC-001, HC-005, HC-008 | 별도 맵을 설치하지 않고 요청 라우팅·실패 진단·채택 지침에 통합합니다. |
| SRC-REF-006 | `리소스/reference/prompt-calibration.md` | core-direct | 루트에 남길 규칙과 가까운 문서로 분리할 세부사항을 구분 | HC-001 | 짧은 라우터의 직접 근거입니다. |
| SRC-ADV-001 | `리소스/openai-advanced/index.md` | core-direct | 최소 팩에서 Standard·Advanced로 승격하는 조건을 명시 | HC-008 | 고급 파일 전체가 아니라 점진적 채택 경계가 Core ADOPTION의 직접 근거입니다. |
| SRC-ADV-002 | `리소스/openai-advanced/repo-template/index.md` | core-direct | 고급 저장소 구성의 복사 순서와 적용 범위를 안전하게 라우팅 | HC-008, HC-014, HC-015 | Core 설치·버전·제거 계약에 복제 경계 원칙을 직접 반영하며 고급 산출물 자체는 조건부입니다. |
| SRC-ADV-003 | `리소스/openai-advanced/repo-template/AGENTS.md` | core-direct | 고급 라우터의 작업 계약과 종료 규칙 중 범용 부분만 유지 | HC-001 | 설치된 짧은 라우터의 직접 근거이며 고급 문서 링크는 존재할 때만 추가합니다. |
| SRC-ADV-004 | `리소스/openai-advanced/repo-template/ARCHITECTURE.md` | core-direct | 실제 도메인·경계·횡단 관심사를 발견 가능한 지도에 기록 | HC-006, standard:architecture-boundary | Core는 최소 구조 질문을 제공하고 계층·경계 검사는 둘 이상의 경계가 생길 때 승격합니다. |
| SRC-ADV-005 | `리소스/openai-advanced/repo-template/docs/DESIGN.md` | deferred | 설계 제안·수락·폐기의 내구적 수명주기를 유지 | standard:decision-lifecycle | 작은 단일 변경에는 별도 설계 체계를 강제하지 않고 장기 결정이 생길 때 추가합니다. |
| SRC-ADV-006 | `리소스/openai-advanced/repo-template/docs/FRONTEND.md` | deferred | UI 상태·접근성·실제 런타임 경로를 검증 | standard:frontend-validation, standard:e2e | 프런트엔드가 있는 프로젝트에서만 적용 가능한 도메인 문서이므로 Core에 강제하지 않습니다. |
| SRC-ADV-007 | `리소스/openai-advanced/repo-template/docs/PLANS.md` | deferred | 활성·완료 계획과 기술 부채의 재개 가능한 수명주기 관리 | standard:plans | 둘 이상의 세션이나 장기 실행 계획이 생길 때만 설치합니다. |
| SRC-ADV-008 | `리소스/openai-advanced/repo-template/docs/PRODUCT_SENSE.md` | deferred | 횡단 제품 판단과 금지 패턴을 내구적으로 기록 | advanced:product-sense | 제품 의사결정이 없는 라이브러리·도구에도 비용을 부과하므로 조건부입니다. |
| SRC-ADV-009 | `리소스/openai-advanced/repo-template/docs/QUALITY_SCORE.md` | deferred | 품질 등급·벤치마크·절제 로그로 하네스 가치를 재검토 | advanced:quality-ablation | 고정 벤치마크와 반복 측정이 있을 때만 의미가 있어 Advanced로 보류합니다. |
| SRC-ADV-010 | `리소스/openai-advanced/repo-template/docs/RELIABILITY.md` | core-direct | 표준 시작·검증 경로와 최소 황금 여정을 명령 계약에 연결 | HC-002, HC-007, advanced:observability | 재현 가능한 명령 계약은 Core에 직접 반영하고 운영 SLO·신호 체계는 조건부로 보류합니다. |
| SRC-ADV-011 | `리소스/openai-advanced/repo-template/docs/SECURITY.md` | merged | 비밀·신뢰하지 않는 입력·외부 행동·의존성의 권한 경계 유지 | HC-001, HC-002, HC-005, standard:security | Core에는 비밀 금지와 안전한 인자 실행을 합치고 프로젝트별 위협 정책은 트리거 시 분리합니다. |
| SRC-ADV-012 | `리소스/openai-advanced/repo-template/docs/design-docs/core-beliefs.md` | merged | 에이전트 우선·저장소 기반·검증 우선 신념을 짧은 운영 규칙에 반영 | HC-001, HC-005 | 별도 신념 문서를 설치하지 않고 라우터와 감사 계약에 통합합니다. |
| SRC-ADV-013 | `리소스/openai-advanced/repo-template/docs/design-docs/index.md` | deferred | 수락·제안·폐기된 결정을 색인하고 상태를 구분 | standard:decision-lifecycle | 내구적 결정이 여러 개 생길 때만 색인이 가치가 있습니다. |
| SRC-ADV-014 | `리소스/openai-advanced/repo-template/docs/exec-plans/active/index.md` | deferred | 활성 계획을 재개 가능한 위치와 형식으로 관리 | standard:plans | 멀티세션 실행 계획이 있을 때 설치합니다. |
| SRC-ADV-015 | `리소스/openai-advanced/repo-template/docs/exec-plans/completed/index.md` | deferred | 완료 계획을 현재 상태와 분리된 내구 이력으로 보존 | standard:plans | 완료 계획 이력이 누적되기 전에는 Git과 영수증으로 충분합니다. |
| SRC-ADV-016 | `리소스/openai-advanced/repo-template/docs/exec-plans/tech-debt-tracker.md` | deferred | 의도적으로 미룬 부채와 재검토 트리거를 추적 | standard:plans | 실제 부채와 재검토 일정이 생길 때만 별도 원장을 추가합니다. |
| SRC-ADV-017 | `리소스/openai-advanced/repo-template/docs/generated/db-schema.md` | deferred | 생성 산출물의 출처·재생성 명령·수동 편집 금지를 기록 | advanced:generated-artifacts | 생성 문서가 있는 프로젝트에만 필요한 패턴입니다. |
| SRC-ADV-018 | `리소스/openai-advanced/repo-template/docs/product-specs/index.md` | deferred | 사용자 동작 명세를 발견 가능한 색인으로 관리 | advanced:product-specs | 사용자 흐름 명세가 여러 개 생길 때 승격합니다. |
| SRC-ADV-019 | `리소스/openai-advanced/repo-template/docs/product-specs/new-user-onboarding.md` | deferred | 관찰 가능한 흐름·인수 조건·실패 상태로 제품 명세 작성 | advanced:product-specs, standard:e2e | 온보딩은 예시 도메인이므로 복제하지 않고 실제 황금 여정이 있을 때 패턴만 적용합니다. |
| SRC-ADV-020 | `리소스/openai-advanced/repo-template/docs/references/design-system-reference-llms.txt` | deferred | 외부 디자인 시스템 지식을 모델 친화적 캐시로 고정 | advanced:reference-cache | 디자인 시스템 의존성이 있을 때만 출처·갱신 계약과 함께 생성합니다. |
| SRC-ADV-021 | `리소스/openai-advanced/repo-template/docs/references/nixpacks-llms.txt` | deferred | 외부 빌드·런타임 문서를 모델 친화적 캐시로 고정 | advanced:reference-cache | Nixpacks를 실제 사용하는 프로젝트에만 적용합니다. |
| SRC-ADV-022 | `리소스/openai-advanced/repo-template/docs/references/uv-llms.txt` | deferred | 외부 패키지·환경 문서를 모델 친화적 캐시로 고정 | advanced:reference-cache | uv를 실제 사용하는 프로젝트에만 적용합니다. |
| SRC-ADV-023 | `리소스/openai-advanced/sops/chrome-devtools-validation-loop.md` | core-direct | 사용자 대면 UI 변경은 BEFORE·AFTER 실제 런타임 증거로 검증 | HC-005, HC-007, standard:frontend-validation | Core 위험 게이트와 VALIDATION의 직접 근거이며 브라우저 도구 설치는 UI 프로젝트에서만 추가합니다. |
| SRC-ADV-024 | `리소스/openai-advanced/sops/encode-knowledge-into-repo.md` | merged | 외부·암묵 지식을 가장 가까운 저장소 산출물과 검사로 이동 | HC-001, HC-004, HC-006, HC-008, HC-012 | 별도 SOP를 복제하지 않고 라우팅·상태·아키텍처·채택·구성 요소 원장에 통합합니다. |
| SRC-ADV-025 | `리소스/openai-advanced/sops/index.md` | reference-only | 상황에 맞는 SOP를 선택하고 적용 범위를 확인 | standard:sop-router, HC-011, HC-013 | 원본 SOP 트리의 라우터이므로 Core 행동으로 과장하지 않고 Source 맵에서 후속 선택 경로를 보존합니다. |
| SRC-ADV-026 | `리소스/openai-advanced/sops/layered-domain-architecture.md` | deferred | 실제 경계가 있을 때 계층 의존 방향을 문서와 검사로 강제 | HC-006, standard:architecture-boundary | Core 아키텍처 지도는 원칙을 보존하되 고정 계층은 범용 기본값과 충돌하므로 다중 도메인·경계가 관찰될 때만 적용합니다. |
| SRC-ADV-027 | `리소스/openai-advanced/sops/observability-feedback-loop.md` | deferred | 쿼리·추론·수정·재시작·재검증을 운영 신호와 연결 | advanced:observability | 로그만으로 부족한 다단계·분산 흐름이 있을 때 메트릭·트레이스와 함께 승격합니다. |
| SRC-SKL-001 | `스킬/index.md` | merged | 지침·상태·검증·범위·세션 수명주기를 하나의 하네스로 감사 | HC-001, HC-003, HC-005 | 스킬 자체를 설치하지 않고 두 분류 축과 운영 통제 원칙을 기존 Core에 통합합니다. |
| SRC-PRJ-001 | `프로젝트/index.md` | reference-only | 여섯 점진 실습의 비교 순서와 학습 목표 제공 | fixture:progressive-curriculum | 실습 지도는 제품 동작이 아니므로 보존하되 Core 계약으로 주장하지 않습니다. |
| SRC-PRJ-002 | `프로젝트/project-01-baseline-vs-minimal-harness/index.md` | reference-only | 프롬프트 단독과 최소 하네스의 차이를 통제된 비교로 확인 | fixture:minimal-adoption, HC-008 | 채택 Fixture 설계의 참고 근거이며 실습 결과 수치를 템플릿 보장으로 사용하지 않습니다. |
| SRC-PRJ-003 | `프로젝트/project-02-agent-readable-workspace/index.md` | reference-only | 저장소 가독성과 핸드오프가 콜드 스타트에 미치는 영향을 비교 | fixture:cold-start, HC-004, HC-006 | 콜드 스타트 Fixture의 참고 근거이며 교육용 골격은 복제하지 않습니다. |
| SRC-PRJ-004 | `프로젝트/project-03-multi-session-continuity/index.md` | reference-only | 진행·핸드오프·멀티세션 연속성을 비교 | fixture:multi-session, HC-003, HC-004 | 상태·인계 설계의 참고 근거이며 별도 진행 파일은 중복 방지를 위해 설치하지 않습니다. |
| SRC-PRJ-005 | `프로젝트/project-04-incremental-indexing/index.md` | reference-only | 런타임 피드백과 범위 제어를 점진적으로 비교 | fixture:incremental-feedback, HC-003, HC-005 | 기능 범위·피드백 Fixture의 참고 근거이며 실습 환경은 Core 의존성이 아닙니다. |
| SRC-PRJ-006 | `프로젝트/project-05-grounded-qa-verification/index.md` | reference-only | 생성자와 평가자 분리가 검증 편향에 미치는 영향을 비교 | fixture:independent-evaluation, advanced:independent-evaluator | 독립 평가자 승격 판단의 실험 근거이며 모든 작업에 다중 역할을 강제하지 않습니다. |
| SRC-PRJ-007 | `프로젝트/project-06-runtime-observability-and-debugging/index.md` | reference-only | 전체 하네스·런타임 관측·클린 종료·절제를 종합 비교 | fixture:observability-capstone, advanced:observability, advanced:quality-ablation | 고급 프로필의 효용을 측정할 캡스톤 참고 자료이며 Core 기본 의존성으로 복제하지 않습니다. |

## 완전성 계약

- 이 표의 Source ID와 경로는 `docs/source-inventory.md`의 65개 행과 정확히
  일치해야 합니다.
- 설치된 Core는 같은 결정을
  `template/core/docs/harness/source-map.json`에서 독립적으로 해석할 수
  있어야 합니다.
- `deferred`는 폐기가 아닙니다. 연결 대상의 트리거가 관찰될 때 검토합니다.
- 원본 파일의 해시·경로가 바뀌면 인벤토리와 이 표, Source 맵을 함께
  재검증합니다.
