# Current State

## 목표

빈 프로젝트를, 어떤 소프트웨어 프로젝트에도 먼저 복제할 수 있는
`Harness Engineering Starter Lite`로 설계·구현합니다.

## 현재 검증된 상태

- 원본 학습 폴더: 읽기 전용으로 취급
- 재귀 인벤토리: 디렉터리 22개, 파일 65개, 총 287,986바이트
- 형식: Markdown 60, TXT 3, JSON 1, shell 1
- 원문 읽기: 65/65 UTF-8 성공
- 첨부·임베드·이미지·심볼릭 링크·빈 파일: 없음
- 동일 해시 중복: 없음
- Obsidian 위키링크: 39개 모두 원본 트리 안에서 해석 가능
- 원장 대조: 내장 원장의 65개 경로·크기·SHA-256 접두사가 기록된 원본
  스냅샷과 일치. 현재 원본 실시간 대조는 이번 환경에서 실행하지 않음
- 자료 처분: 65행 결정표와 설치본 독립 Source map 일치
  (`core-direct` 28, `merged` 8, `deferred` 19, `reference-only` 10)
- 복제 패키지: `template/core/` 21개 파일, Core 버전 `0.3.0`
- 지침 진입점: root/Core `CLAUDE.md`의 첫 비어 있지 않은 줄이
  `@AGENTS.md`이며 validator와 설치본 audit가 드리프트를 거부
- 커뮤니케이션 계약: Core `AGENTS.md`가 `docs/COMMUNICATION.md`로 연결되고,
  한국어 존댓말·쉬운 설명·간결성·선택적 시각화·증거 경계·자기점검을 요구
- 자기개선 계약: 반복·재현 가능한 에이전트·하네스·루프 구조 결함을 사용자
  정정·반복 실패·문서/실행 불일치·최종 응답 시점에 확인하고, 별도 명령 없이
  `BOOT-001` 경로에서 한 번만 최소 수정·집중 검증한 뒤 종료. 명시적 변경
  금지와 제품·외부·파괴적·Git 경계는 유지
- 자기개선 드리프트: Core `AGENTS.md`와 `docs/COMMUNICATION.md`의 버전 표식을
  설치본 audit가 검사하며, 상시 권한·중지·범위·WIP·실행 예산 문구가 빠지면
  WHAT/WHY/FIX 오류로 거부
- 호출형 건강 감사: `.agents/skills/audit-harness-health/SKILL.md` 한 곳에
  읽기 전용 빠른·집중·깊은 감사 절차를 두고, Claude에는 1 KiB 미만의 텍스트
  포인터만 설치. 설치본 audit가 정본·라우팅·크기·중복·드리프트를 거부
- 컨텍스트 예산: `AGENTS.md` 8 KiB, `CLAUDE.md` 4 KiB,
  `COMMUNICATION.md`·`STATE.md` 각 16 KiB 상한. 일반 시작의 정적 필수 읽기는
  6개·19,317바이트에서 2개·6,854바이트로 축소되고 bounded cold-start JSON은
  설치 Fixture에서 1,174바이트. 7,889바이트 감사 정본은 호출할 때만 읽음
- 운영 이력: 기능별 최신 상태 전환 20개와 영수증 참조 5개만 원장에 유지하며
  과거 영수증 파일과 Git 이력은 보존
- 운영체제 진입점: POSIX `init.sh`, Windows PowerShell 5.1+ `init.ps1`
- Python 선택: PowerShell에서 venv/Conda, `py -3`, `python`, `python3`
  순으로 3.10+를 검사하며 probe 중 자동 설치를 막고 환경을 원복
- 설치 경로: `scripts/install_core.py`, 입력 대상의 기존 모든 segment와
  관리 하위 경로의 심볼릭 링크·Windows junction/reparse point·프로젝트 밖
  경로 차단, Windows 대소문자 alias·예약 이름·ADS·후행 점/공백 거부,
  기존 파일·막힌 상위 경로 덮어쓰기 거부
- 수명주기: `.harness/install-manifest.json` 기반 install·dry-run
  upgrade·수동 병합 승인·remove·backup·실패 rollback 계약, downgrade·
  major·pre-1 minor 자동 전환 거부
- 같은 버전 no-op: 파일 변경·버전 변경·승인된 원장 전환이 모두 없으면
  manifest·timestamp·backup을 쓰지 않고 종료. 실제 변경이 있으면 기존
  backup·rollback·증거 stale 계약을 유지
- 배포 경계: root/Core `VERSION`, MIT `LICENSE`, upstream 귀속 `NOTICE` 일치
- 설정 계약: `harness.config.json`의 안전한 인자 배열, `argv[0]` 전용
  `{python}` current-interpreter 토큰, 활성 위험 프로필
- 실행 계약: 고유 gate ID, repo 내부 `cwd`, timeout, stdout/stderr별 bounded
  tail, 비밀 마스킹, 누락 실행 파일의 실행 가능한 오류, POSIX process group,
  Windows CTRL_BREAK → 절대 경로 `taskkill /T /F` → direct kill 순서
- 상태 기계: `not_started → active → blocked/passing`, 회귀 시 `reopen`
- 상태 일치: 전환 시 `docs/STATE.md` 관리 블록 동기화, 드리프트 탐지·복구
- 기능 검증: 모든 요구사항을 실제 `{level, command_id}`에 연결하고 미연결·
  프로필 밖·미실행 gate 거부
- 증거: `.harness/evidence/` schema-v4 영수증, 영수증 자체 hash·완전한
  실행 구조·effective argv hash·전체 설정 provenance·실행 계약 freshness·
  검증 정의·정확한 tracked file digest·Git revision·OS/Python
  implementation/major.minor runtime 기록
- 신선도: 최신 영수증을 현재 실행 V0~Vn gate·선택/시작 profile·runner·공통
  제어면·검증·파일·revision·runtime과 엄격 대조하되, 미실행 gate와 무관한
  risk profile 변경은 허용. stale 상태는 `reopen` 뒤 재검증하고 schema-v2/v3는
  schema-v4 재검증 후 과거 이력으로만 보존
- 완료 게이트: V0~V4 연속 단계, 위험 하향 금지, 실패 시 상태 유지
- 근거 링크 의미: Source map의 연결 대상은 넓은 처분·영향 범위,
  Component `sources`는 좁은 직접 근거이며 부분집합 계약을 validator가 검사
- Fixture: 빈 임시 프로젝트 설치·실제 patch upgrade·rollback·버전 거부·
  link/junction/reparse·Windows path alias, 운영체제별 init 계약, 콜드 스타트,
  Claude import 드리프트, WIP·영수증 불변식·schema migration,
  hash/digest/Git/runtime freshness,
  호출형 Skill 배포·포인터·읽기 전용·계약 드리프트,
  자식 process-tree timeout·cwd·로그 제한, 부분 실패 회수,
  POSIX·Python·Node 대표 스택, 실패·클린 상태·고위험 게이트 검증
- 실제 외부 채택: `repos_hyeonbungi`의 독립 Git 프로젝트 두 곳에서 기존 제품
  파일 해시를 보존한 채 21개 Core 설치·설정·반복 init·BOOT-001 완료·감사·
  같은 버전 no-op을 검증하고, 두 프로젝트를 작업 위치에서 제거
- 프로젝트 기준선: 네이티브 Windows에서 PowerShell 7.6.3과 Windows
  PowerShell 5.1의 `init.ps1`로 각각 필수 산출물 36/36, 내장 원장 65/65 추적,
  Core 감사, 동적 Fixture 총 45개 중 44개 통과, POSIX 전용 `sh` Fixture 1개
  명시적 skip
- 현재 프로젝트: 로컬 `main` Git 저장소와 공개 원격
  `https://github.com/hyeonbungi/harness-engineering-starter-lite`를 사용

## 이번 단계의 결정

- `HST-008`을 네이티브 Windows에서 재검증해 완료했습니다. 루트 구성요소
  경로는 플랫폼 독립 `/` 형식으로 정규화하고, 정확한 `..` 세그먼트는 공통
  resolved-root 경계에서 거부해 플랫폼별 오류 계약을 통일했습니다. 독립 임시
  Git 프로젝트에서 제품 파일 해시를 보존한 21개 Core 설치·설정·반복 init·
  BOOT-001 완료·같은 버전 no-op까지 확인했습니다.
- `HST-015`를 완료했습니다. 실제 외부 Git 프로젝트의 설치·설정·완료로 제품
  파일 보존과 독립 실행을 확인했고, 같은 버전 무변경 upgrade가 남기던
  manifest-only 백업과 timestamp 쓰기를 제거했습니다. 실제 파일 또는 원장
  전환은 계속 backup 뒤 수행합니다.
- `HST-014`를 완료했습니다. Codex와 공용 Agent Skills가 탐색하는
  `.agents/skills`에 호출형 감사 스킬 정본을 두고, Claude 탐색 경로에는
  정본을 읽는 작은 텍스트 포인터만 설치했습니다. 감사 중 자동 개선은
  수행하지 않으며 기존 reparse-point 거부 계약을 유지합니다.
- `HST-013`을 완료했습니다. 재현·반복되는 에이전트·하네스·루프 구조 결함은
  별도 명령 없이 저장소 내부에서 한 번 자동 개선하되, 명시적 중지·제품 범위·
  외부·파괴적 경계, WIP=1과 완료 증거를 유지합니다.
- `HST-012`에서 기존 Core 파일만 사용해 자기개선 종료 루프, progressive
  startup, 항상 읽는 파일의 byte 상한과 기능별 최근 이력 window를 구현하고
  전체 기준선으로 검증했습니다.
- 일반 세션은 전체 원장 대신 `AGENTS.md`·현재 `STATE`·cold-start 요약으로
  기능 하나를 고르고 관련 문서만 읽습니다. 기준선과 종료에는 전체 검증,
  구현 중에는 집중 검사를 사용합니다.
- 크기 상한을 통과 목적으로 높이는 것은 수정으로 인정하지 않으며, 중복 통합과
  현재 사실 교체를 요구합니다.
- 오래된 영수증 참조를 운영 원장에서 축약해도 실제 영수증 파일은 삭제하지
  않습니다.
- 이번 변경은 미커밋 Core `0.3.0`에 포함하며, `0.2.x` 채택본은 기존 정책대로
  검토된 수동 전환과 schema-v4 재검증을 사용합니다.
- `HST-006` Standard/Advanced 선택형 모듈은 사용자 결정에 따라 현재
  `0.3.0` 릴리스에서도 `out_of_scope`로 유지합니다.
- 네이티브 Windows 실기 결과는 Windows/PowerShell 환경이 생길 때 추가할
  향후 검증 증거이며, 현재 릴리스의 다음 작업이나 완료 차단 조건이 아닙니다.
- 기본 배포물은 `core` 프로필로 작게 유지하고, 고급 문서·관측·역할 분리는
  필요할 때 선택형 프로필로 올립니다.

## 열린 위험

- 원본 강의 일부의 수치와 제품 버전은 교육용 서술이며 최신성 검증을 하지
  않았습니다. 템플릿은 수치가 아니라 반복되는 운영 원칙을 채택합니다.
- Core 실행기는 두 운영체제 모두 Python 3.10+를 요구합니다. Python 자체가
  없는 환경의 자동 설치는 범위 밖입니다.
- 네이티브 Windows에서 PowerShell 7.6.3과 Windows PowerShell 5.1의 루트·
  설치본 init, 자식 프로세스 timeout과 대표 채택 흐름을 실행했습니다. 실제
  junction 생성은 수행하지 않았고, reparse attribute와 거부 동작은 결정적
  Fixture로 검증합니다.
- 모든 Windows reparse point를 보수적으로 거부하므로 provider-managed
  mount에서 오탐할 수 있습니다. UNC·네트워크 파일시스템 원자성도 자동
  보장 범위가 아닙니다.
- Node 대표 Fixture는 Node가 설치된 환경에서 실행되며, 미설치 환경에서는
  명시적으로 skip합니다. 현재 환경에서는 실제 통과했습니다.
- Fixture는 일반 명령·상태·게이트와 대표 스택을 검증하지만, 실제 제품별
  E2E 품질은 채택 프로젝트가 올바른 명령·binding·tracked file을 넣어야
  확보됩니다.
- 실행 계약 digest는 미실행 gate와 무관한 profile만 제외합니다. 임의 gate가
  프로젝트 메타데이터·setup/start·경로·startup profile을 간접 참조할 수 있어
  이 공통 제어면은 안전하게 보수적으로 포함합니다.
- 저장소는 자기개선 발동 확인 시점·상시 권한·검증기를 제공하지만, 호스트의
  상위 정책이 쓰기를 금지하거나 모델이 의미적 결함을 인식하지 못하는 경우까지
  자동 수정을 강제할 수는 없습니다. 이때는 결함과 최소 수정안을 보고합니다.
- 정적 검사는 Skill 등록·정본·포인터 계약을 증명하지만, 모든 Codex·Claude
  버전이 호출 문구를 동일하게 탐색하고 감사 지침을 의미적으로 준수하는지는
  보장하지 않습니다. 클라이언트나 모델 변경 뒤에는 깨끗한 설치본에서 실제
  호출을 확인합니다.
- 원본 자료가 보고한 MIT 표기는 출처 고지에 명시했으며, 별도 upstream
  재배포의 법적 판단을 대신하지 않습니다.

## 다음 행동

- 필수 active 기능은 없습니다. 다음 사용자 목표가 생기면 우선순위가 가장 높은
  기능 하나만 엽니다.
