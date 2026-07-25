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
- 원장 대조: 65개 경로·크기·SHA-256 접두사가 현재 원본과 일치
- 자료 처분: 65행 결정표와 설치본 독립 Source map 일치
  (`core-direct` 28, `merged` 8, `deferred` 19, `reference-only` 10)
- 복제 패키지: `template/core/` 18개 파일, Core 버전 `0.2.1`
- 지침 진입점: root/Core `CLAUDE.md`의 첫 비어 있지 않은 줄이
  `@AGENTS.md`이며 validator와 설치본 audit가 드리프트를 거부
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
- 증거: `.harness/evidence/` schema-v3 영수증, 영수증 자체 hash·완전한
  실행 구조·effective argv hash·설정·검증 정의·정확한 tracked file
  digest·Git revision·OS/Python implementation/major.minor runtime 기록
- 신선도: 최신 영수증을 현재 hash·digest·revision·runtime과 엄격 대조하고,
  stale 상태는 `reopen` 뒤 재검증. schema-v2는 재검증 후 과거 이력으로만 보존
- 완료 게이트: V0~V4 연속 단계, 위험 하향 금지, 실패 시 상태 유지
- 근거 링크 의미: Source map의 연결 대상은 넓은 처분·영향 범위,
  Component `sources`는 좁은 직접 근거이며 부분집합 계약을 validator가 검사
- Fixture: 빈 임시 프로젝트 설치·실제 patch upgrade·rollback·버전 거부·
  link/junction/reparse·Windows path alias, 운영체제별 init 계약, 콜드 스타트,
  Claude import 드리프트, WIP·영수증 불변식·schema migration,
  hash/digest/Git/runtime freshness,
  자식 process-tree timeout·cwd·로그 제한, 부분 실패 회수,
  POSIX·Python·Node 대표 스택, 실패·클린 상태·고위험 게이트 검증
- 프로젝트 기준선: `./init.sh`에서 필수 산출물 33/33, 현재 원본
  65/65 hash, Core 감사, 동적 Fixture 총 38개 중 37개 통과, 네이티브
  PowerShell Fixture 1개는 현재 비-Windows 호스트에서 명시적 skip
- 현재 프로젝트: 로컬 `main` Git 저장소와 공개 원격
  `https://github.com/hyeonbungi/harness-engineering-starter-lite`를 사용

## 이번 단계의 결정

- `HST-007` Core 신뢰성·배포 계약 보강을 실행 증거와 함께 완료했습니다.
- `HST-008` 네이티브 Windows PowerShell·프로세스·경로 어댑터를
  `0.2.0`으로 구현하고 현재 호스트에서 가능한 검증을 완료했습니다.
- `HST-009`에서 root/Core `CLAUDE.md`를 `@AGENTS.md` import로 축소하고,
  드리프트 거부 검사를 추가한 `0.2.1` patch를 검증했습니다.
- `HST-006` Standard/Advanced 선택형 모듈은 사용자 결정에 따라 현재
  `0.2.1` 릴리스에서도 `out_of_scope`로 유지합니다.
- 네이티브 Windows 실기 결과는 Windows/PowerShell 환경이 생길 때 추가할
  향후 검증 증거이며, 현재 릴리스의 다음 작업이나 완료 차단 조건이 아닙니다.
- 원본 자료의 완전성 원장과 설계 추적성을 유지합니다.
- 기본 배포물은 `core` 프로필로 작게 유지하고, 고급 문서·관측·역할 분리는
  필요할 때 선택형 프로필로 올립니다.
- 인간용 현재 상태는 이 파일 하나로 제한하고, 기능 상태는
  `feature_list.json`에 둡니다.
- 특정 언어·프레임워크·CI·클라우드는 기본 의존성으로 선택하지 않습니다.
- 명령은 셸 문자열이 아닌 인자 배열로 실행하고 설치기는 기존 파일을
  덮어쓰지 않습니다.
- 과거 통과 영수증은 보존하되 최신 영수증만 현재 증거로 엄격 검사하고,
  회귀한 기능은 다시 엽니다.
- `0.1.x → 0.2.0`은 pre-1.0 minor 전환이므로 자동 upgrade를 거부하고
  별도 검토한 수동 채택과 schema-v3 재검증을 요구합니다.
- `0.2.0 → 0.2.1`은 설치 원장의 로컬 변경 보호를 거치는 호환 patch
  upgrade입니다.

## 열린 위험

- 원본 강의 일부의 수치와 제품 버전은 교육용 서술이며 최신성 검증을 하지
  않았습니다. 템플릿은 수치가 아니라 반복되는 운영 원칙을 채택합니다.
- Core 실행기는 두 운영체제 모두 Python 3.10+를 요구합니다. Python 자체가
  없는 환경의 자동 설치는 범위 밖입니다.
- 현재 macOS 호스트에는 `pwsh`/`powershell`이 없어 PowerShell 5.1 파싱·실행,
  실제 Windows `taskkill`, 실제 junction 경계를 실행하지 못했습니다.
  정적·모의 검증과 Windows에서 자동 실행되는 조건부 Fixture는 준비됐지만,
  네이티브 Windows 통과 결과는 환경이 마련될 때 추가할 향후 검증 증거로만
  남깁니다. 이는 현재 구현 미완료나 `0.2.1` 릴리스 차단을 뜻하지 않습니다.
- 모든 Windows reparse point를 보수적으로 거부하므로 provider-managed
  mount에서 오탐할 수 있습니다. UNC·네트워크 파일시스템 원자성도 자동
  보장 범위가 아닙니다.
- Node 대표 Fixture는 Node가 설치된 환경에서 실행되며, 미설치 환경에서는
  명시적으로 skip합니다. 현재 환경에서는 실제 통과했습니다.
- Fixture는 일반 명령·상태·게이트와 대표 스택을 검증하지만, 실제 제품별
  E2E 품질은 채택 프로젝트가 올바른 명령·binding·tracked file을 넣어야
  확보됩니다.
- 전체 config digest는 안전하게 보수적이지만 무관한 gate 변경도 기존 최신
  영수증을 stale로 만들 수 있습니다. 필요하면 기능 단위 config digest로
  후속 최적화합니다.
- 원본 자료가 보고한 MIT 표기는 출처 고지에 명시했으며, 별도 upstream
  재배포의 법적 판단을 대신하지 않습니다.

## 다음 행동

- 현재 릴리스의 필수 후속 작업은 없습니다. Core `0.2.1`을 현재 범위에서
  마감합니다.
- 네이티브 Windows 실행 결과는 Windows/PowerShell 환경이 생길 때 추가할
  향후 검증 증거이며, 현재 완료 상태를 열어 두지 않습니다.
