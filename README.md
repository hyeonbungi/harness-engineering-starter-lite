# Harness Engineering Starter Lite

어떤 소프트웨어 프로젝트에도 먼저 복제해 사용할 수 있는, 작고 검증 가능한
하네스 엔지니어링 스타터를 만드는 저장소입니다.

원본 학습 자료 65개를 전수 분석한 설계 기준선과, 새 프로젝트에 안전하게
설치할 수 있는 복제형 Core 프로필을 함께 제공합니다. 제품 스택은 가정하지
않으며 하네스 런타임은 Python 표준 라이브러리만 사용합니다.

## 현재 산출물

- [`AGENTS.md`](AGENTS.md): 이 저장소에서 작업하는 에이전트의 짧은 라우터
- [`CLAUDE.md`](CLAUDE.md): Claude Code가 `AGENTS.md`를 가져오는 얇은 진입점
- [`feature_list.json`](feature_list.json): 구현 범위와 검증 상태의 기계 판독 원장
- [`docs/STATE.md`](docs/STATE.md): 현재 상태, 위험, 다음 행동의 단일 인간용 표면
- [`docs/source-inventory.md`](docs/source-inventory.md): 원본 65개 파일의 전수 원장
- [`docs/source-analysis.md`](docs/source-analysis.md): 자료 전체에서 추출한 원칙과 긴장 관계
- [`docs/source-disposition.md`](docs/source-disposition.md): 65개 자료별 반영·통합·보류 결정표
- [`docs/design-proposal.md`](docs/design-proposal.md): 템플릿 구성과 근거 추적 설계
- [`template/core/`](template/core/): 실제 프로젝트에 복제할 Core 프로필
- [`scripts/install_core.py`](scripts/install_core.py): 설치 원장 기반 설치·업그레이드·제거 도구
- [`VERSION`](VERSION), [`LICENSE`](LICENSE), [`NOTICE`](NOTICE): 배포 버전과
  라이선스·귀속 계약
- [`init.sh`](init.sh), [`init.ps1`](init.ps1): POSIX·Windows 기준선
  및 Fixture 검증 진입점

## Core 프로필 설치

```bash
python3 scripts/install_core.py /absolute/path/to/project --dry-run
python3 scripts/install_core.py /absolute/path/to/project
python3 scripts/install_core.py /absolute/path/to/project --upgrade --dry-run
python3 scripts/install_core.py /absolute/path/to/project --remove --dry-run
```

Windows PowerShell에서는 같은 명령의 `python3` 대신 설치된 Python
3.10+(`py -3` 또는 `python`)을 사용합니다.

설치기는 입력 대상과 관리 경로의 심볼릭 링크·Windows junction/reparse
point, 프로젝트 밖으로 해석되는 경로, 대소문자 alias, 기존 파일이나 막힌
상위 경로를 쓰기 전에 거부합니다. 성공하면
`.harness/install-manifest.json`에 버전과 18개 관리 파일 digest를 기록합니다.
업그레이드와 제거는 이 원장에서 소유권과 로컬 변경 여부를 증명할 수 있는
파일만 다룹니다.

설치 후 다음 순서로 설정합니다.

1. `harness.config.json`의 프로젝트 정보와 안전한 명령 배열을 채웁니다.
2. 사용할 V0~V4 게이트와 위험 프로필만 활성화합니다.
3. `feature_list.json`, `docs/STATE.md`, `docs/ARCHITECTURE.md`,
   `docs/VALIDATION.md`의 플레이스홀더를 교체합니다.
4. POSIX에서는 `./init.sh --setup`, Windows PowerShell에서는
   `.\init.ps1 -Setup`을 실행한 뒤 같은 어댑터를 한 번 더 실행합니다.
5. 어댑터가 선택한 Python으로 `scripts/harness.py cold-start --json`을
   실행해 다섯 가지 콜드 스타트 답변을 확인합니다.

Claude Code는 `CLAUDE.md`의 `@AGENTS.md` import를 통해 같은 공통 규칙을
읽습니다. 공통 규칙을 두 파일에 복제하지 말고 Claude 전용 지침이 실제로
필요할 때만 import 아래에 추가합니다.

자세한 절차는
[`template/core/docs/harness/ADOPTION.md`](template/core/docs/harness/ADOPTION.md)에
있습니다.

## 상태와 완료

```bash
python3 scripts/harness.py state activate BOOT-001
python3 scripts/harness.py state block BOOT-001 --reason "원인과 복구 조건"
python3 scripts/harness.py state reopen BOOT-001 --reason "재개 이유"
python3 scripts/harness.py complete BOOT-001 --risk local_code
```

`complete`는 위험 프로필이 요구하는 연속 V0~V4 게이트를 실행하고, 클린
상태를 확인하고, `.harness/evidence/`에 영수증을 쓴 뒤에만 상태를
`passing`으로 바꿉니다. 기능의 각 검증 요구사항은 실제
`level/command_id`에 연결되어야 하며 해당 명령이 실행되지 않으면 완료할 수
없습니다. 최신 영수증은 현재 설정·검증 정의·추적 파일 digest, Git
revision, OS·Python runtime identity를 다시 대조합니다. 회귀나 증거 만료가
발생하면 이전 영수증을 보존한 채 `reopen`으로 다시 엽니다.

## 스타터 자체 검증

```bash
./init.sh
```

Windows PowerShell에서는 `.\init.ps1`을 사용합니다.

이 명령은 Core 구조·65개 근거 원장과 동적 빈 Fixture 설치를 검증합니다.
Fixture는 설치·업그레이드·제거와 link/junction 경계, 설정 오류, 운영체제별
init 멱등성, 콜드 스타트, WIP=1, 기능별 gate binding, 증거 신선도, 상태
회귀·동기화, timeout·bounded/redacted 로그, 클린 상태와 V0~V4 영수증을
실행합니다. POSIX 셸, Python 표준 라이브러리, 설치된 경우 Node 내장 테스트
스택도 대표 채택 경로로 검증합니다. Windows 전용 분기는 모든 환경에서
정적·모의 Fixture로 검사하고, PowerShell이 있는 Windows runner에서는
실제 `init.ps1`과 자식 프로세스 종료를 추가 실행합니다.

## 범위

포함:

- 저장소를 단일 진실 원천으로 만드는 최소 제어면
- 짧은 지침과 점진적 공개
- WIP=1, 실행 증거 기반 완료, 세션 연속성
- 스택 중립적인 명령 설정과 위험 기반 V0~V4 완료 게이트
- 제한된 `cwd`·timeout·출력 상한·비밀 마스킹을 적용한 명령 runner
- POSIX shell과 네이티브 Windows PowerShell 5.1+ 시작 어댑터
- POSIX process group과 Windows process tree의 timeout 종료
- 원자적 상태 전환과 신선도 검사가 가능한 근거 영수증
- 각 구성 요소에서 원본 자료까지 역추적 가능한 독립 Source map
- SemVer, MIT 라이선스, NOTICE, manifest 기반 업그레이드·제거 계약

아직 포함하지 않음:

- 특정 언어·패키지 관리자·CI 제공자
- 멀티 에이전트 오케스트레이터와 독립 평가자
- OpenTelemetry, 브라우저 자동화, 대시보드의 기본 설치
- Core 설치기가 대상 프로젝트의 Git 초기화, 커밋, 원격 저장소를 자동 생성

이 항목들은 필요성이 확인된 뒤 선택형 프로필로 추가합니다. Core의
트레이드오프는 두 운영체제 모두 Python 3.10+ 실행 환경이 필요하고,
안전을 위해 Windows reparse point를 넓게 거부한다는 점입니다. UNC·네트워크
파일시스템의 원자성은 보장 범위가 아니며, 실제 제품별 E2E 명령은 채택
프로젝트가 구성해야 합니다.
