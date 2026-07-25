# Starter Design Proposal

## 구현 상태

2026-07-25 현재 아래 항목은 제안이 아니라 구현·Fixture 검증된 상태입니다.

| 항목 | 구현 | 검증 |
| --- | --- | --- |
| 복제 가능한 Core 프로필 | `template/core/` | 빈 임시 프로젝트 설치 |
| 안전한 설정 파일 | `harness.config.json` 인자 배열 | 플레이스홀더·비활성 프로필 거부 |
| 상태 전환·영수증 | `scripts/harness.py state/complete` | WIP=1, 차단, 재개, 회귀 |
| 콜드 스타트 | `cold-start --json` | 5개 질문의 구조화 답변 |
| 단계별 완료 게이트 | V0~V4 위험 프로필 | 실패 차단, 위험 하향 금지, 클린 상태 |
| 기능별 실행 검증 | `verification.bindings` | 누락·프로필 밖·미실행 gate 거부 |
| 증거 신선도 | receipt·config·verification·tracked file hash와 revision | 불완전·변조·stale `passing` 거부·재개 |
| 제한 runner | repo `cwd`, timeout, bounded/redacted log | hang·대출력·누락 실행 파일 Fixture |
| 네이티브 Windows 어댑터 | `init.ps1`, current-Python token, Windows process tree | 정적·모의 Windows Fixture와 조건부 네이티브 실행 |
| 자료 처분·독립 해석 | 65행 결정표 + 설치본 `source-map.json` | 원장 65/65·양방향 연결 |
| 배포 수명주기 | `VERSION`, `LICENSE`, `NOTICE`, install manifest | 실제 patch upgrade·version guard·rollback·remove Fixture |

스타터 자체의 `./init.sh` 또는 `.\init.ps1`이 이 동작을 동적 Fixture에서
반복 검증합니다.

## 결론

가장 단순하게 재사용 가능한 형태는 **작은 core 프로필 + 조건부 모듈 +
기계 검증되는 근거 원장**입니다. 고급 팩 전체를 기본으로 복사하지 않고,
콜드 스타트·범위·완료·연속성 문제를 직접 막는 구성만 항상 설치합니다.

## 설계 목표

- 특정 언어·프레임워크·클라우드에 종속되지 않음
- 새 세션이 5개 콜드 스타트 질문에 답할 수 있음
- WIP=1과 증거 기반 완료가 기계적으로 검사됨
- 사람용 상태 문서가 중복되지 않음
- 위험이 커질 때만 검증·문서·관측 모듈을 승격
- 모든 구성 요소의 출처·적용 조건·재검토·롤백을 추적

## 구현 구조

```text
project/
├── AGENTS.md
├── CLAUDE.md                    # 선택: AGENTS.md를 가리키는 얇은 포인터
├── VERSION
├── LICENSE
├── NOTICE
├── harness.config.json          # 프로젝트별 명령·경로, 비밀 금지
├── feature_list.json            # 범위·상태·검증·증거의 기계 진실
├── init.sh                      # POSIX 진입점
├── init.ps1                     # Windows PowerShell 진입점
├── scripts/
│   └── harness.py               # stdlib 기반 검사·상태 전환·명령 실행
└── docs/
    ├── STATE.md                 # bounded current snapshot
    ├── ARCHITECTURE.md          # 실제 경계가 생긴 뒤 채움
    ├── VALIDATION.md            # 위험별 검증 레벨과 황금 여정
    ├── SECURITY.md              # 선택형: 별도 정책이 필요한 경우
    ├── decisions/               # 내구적 근거가 필요할 때만
    ├── plans/                   # 멀티세션 작업일 때만
    └── harness/
        ├── components.json      # 구성 요소 추적 원장
        ├── source-map.json      # 설치본에서 독립 해석 가능한 65개 Source 맵
        ├── SOURCES.md           # 출처·라이선스 경계
        ├── LIFECYCLE.md         # 버전·업그레이드·제거 계약
        └── ADOPTION.md          # 복제·설정·업그레이드·제거 절차
```

## 프로필

### Core: 항상 설치

| 구성 | 역할 | 근거 | 트레이드오프 |
| --- | --- | --- | --- |
| 짧은 `AGENTS.md` | 요청·시작·작업·완료·종료 라우팅 | `SRC-CH-003..004`, `SRC-TPL-001`, `SRC-REF-006`, `SRC-ADV-003` | 너무 짧으면 공백, 너무 길면 SNR 저하 |
| `harness.config.json` | 설치·시작·집중·전체 검증 명령을 안전한 배열로 선언 | `SRC-CH-002`, `SRC-CH-006`, `SRC-TPL-008`, `SRC-ADV-010` | 설정 파일 하나 증가, 대신 셸 `eval` 제거 |
| `feature_list.json` | WIP=1, 상태, 검증, 증거, 근거 | `SRC-CH-007..008`, `SRC-TPL-006` | 작은 작업에도 약간의 기록 비용 |
| `docs/STATE.md` | 현재 목표·검증·위험·다음 행동 | `SRC-CH-005`, `SRC-TPL-003`, `SRC-TPL-010` | 이력 로그로 비대해지지 않게 bounded 유지 |
| `init.sh`·`init.ps1` + validator | 운영체제별 멱등 프리플라이트와 fail-loud 진단 | `SRC-CH-006`, `SRC-TPL-008`, `SRC-REF-001`, `SRC-REF-004` | 래퍼 2개를 동기화해야 하지만 네이티브 시작 경로가 명확함 |
| `docs/ARCHITECTURE.md`·`VALIDATION.md` | 콜드 스타트 구조·검증 요약 | `SRC-CH-003`, `SRC-CH-009..010` | Core에는 짧은 요약만 두고 필요할 때 확장 |
| Source·Component 원장 | 65개 근거와 18개 구성 요소의 양방향 추적 | `SRC-REF-002`, `SRC-ADV-025..026` | 원장 유지 비용 대신 독립 감사 가능 |
| 버전·라이선스·수명주기 | 안전한 복제·갱신·제거 경계 | `SRC-RES-001`, `SRC-ADV-002` | manifest 파일 증가, 대신 로컬 변경 보호 |

`CLAUDE.md`는 `AGENTS.md`를 복제하지 않고 짧은 포인터로 둡니다. 여러
에이전트 진입점을 지원하면서 규칙 드리프트를 줄이기 위한 선택입니다.

### Standard: 트리거가 있을 때 설치

| 트리거 | 추가 구성 | 근거 |
| --- | --- | --- |
| 둘 이상의 도메인·계층 | Core `ARCHITECTURE.md` 확장, 로컬 경계 문서, 경계 검사 | `SRC-CH-003`, `SRC-CH-010`, `SRC-ADV-004`, `SRC-ADV-026` |
| 크로스 컴포넌트·사용자 대면 변경 | Core `VALIDATION.md` 확장, 황금 여정, V2/V3 게이트 | `SRC-CH-009..010`, `SRC-ADV-006`, `SRC-ADV-023` |
| 비밀·외부 입력·운영 동작 | `docs/SECURITY.md` | `SRC-ADV-011` |
| 둘 이상의 세션 | `docs/plans/active/`, 결정 기록 | `SRC-CH-005`, `SRC-ADV-007`, `SRC-ADV-014..016` |

### Advanced: 관찰된 병목이 있을 때 설치

- 제품 명세와 제품 판단: `SRC-ADV-008`, `SRC-ADV-018..019`
- 품질 점수와 절제 벤치마크: `SRC-CH-012`, `SRC-ADV-009`
- 생성·외부 참고 캐시: `SRC-ADV-017`, `SRC-ADV-020..022`
- 로그·메트릭·트레이스: `SRC-CH-011`, `SRC-ADV-010`, `SRC-ADV-027`
- 독립 평가자·루브릭: `SRC-CH-009`, `SRC-TPL-005`, `SRC-PRJ-006`

Standard/Advanced는 후속 설계 카탈로그로만 유지합니다. 이를 패키징하는
`HST-006`은 Core `0.2.0`의 `out_of_scope`이며, 관찰된 병목과 명시적
재범위 결정이 있는 미래 릴리스에서만 다시 엽니다.

## 실행 계약

명령을 셸 문자열이 아니라 인자 배열로 저장하여 quoting과 명령 주입 위험을
줄입니다.

```json
{
  "schema_version": 1,
  "runner": {
    "default_timeout_seconds": 300,
    "max_output_bytes": 65536
  },
  "gates": {
    "V1": {
      "commands": [
        {
          "id": "focused-contract",
          "argv": ["{python}", "-m", "unittest", "tests/test_contract.py"],
          "cwd": ".",
          "timeout_seconds": 60,
          "why": "The changed contract must remain valid.",
          "fix": "Repair the contract or its focused test."
        }
      ]
    }
  },
  "risk_profiles": {
    "local_code": {"enabled": true, "levels": ["V0", "V1"]}
  }
}
```

명령은 인자 배열로 실행하며 repo 내부 `cwd`, 양수 timeout, 출력 상한을
적용합니다. 빈 필수 레벨은 “성공”이 아니라 미설정입니다. 기능의 각
`verification`은 `{level, command_id}`에 연결하고, 신선도를 판정할 정확한
`tracked_files`를 선언합니다.

`{python}`은 `argv[0]`에서만 허용되는 배포 토큰이며 실행 시 현재
`harness.py`를 구동한 `sys.executable`로 치환됩니다. 따라서 config digest는
운영체제에 독립적이고, 실제 실행 argv와 runtime identity는 영수증에 남습니다.
POSIX는 새 session/process group을 만들고 timeout 때 group signal을
보냅니다. Windows는 새 process group을 만들고 CTRL_BREAK를 시도한 뒤
절대 경로의 `taskkill.exe /T /F`, 마지막으로 직접 kill 순서로 종료합니다.

## 상태 전환 제안

```text
not_started -> active -> passing
                    \-> blocked
blocked -> active
passing -> active | blocked   # 회귀 또는 증거 만료
```

규칙:

- `active`는 최대 1개
- `passing`에는 검증 명령, 시간, 종료 코드, 대상 revision 또는 파일 집합,
  증거 위치가 필요
- 검증 정의를 바꾼 변경은 해당 기능을 자동 재검토
- 과거 통과 영수증은 보존하지만 현재 상태와 혼동하지 않음
- 상태 전환은 validator 또는 명시적 명령을 통해 수행

## 검증 레벨 제안

| 레벨 | 목적 | 기본 적용 |
| --- | --- | --- |
| V0 | 문서·JSON·셸 문법, 구조 검사 | 모든 변경 |
| V1 | 집중 테스트·린트·타입 검사 | 코드 변경 |
| V2 | 시작·런타임·통합 경로 | 런타임 또는 경계 변경 |
| V3 | E2E 황금 여정 | 사용자 대면·크로스 컴포넌트·외부 효과 |
| V4 | 성능·보안·복구 | 위험 평가가 요구할 때 |

완료 영수증은 receipt 자체 hash, 실행·생략 레벨, 실제 command ID,
redacted effective argv digest, `cwd`·timeout·출력 크기, 설정·검증·파일
digest, revision, OS·Python runtime identity를 기록합니다.

## 근거 추적 계약

템플릿의 `docs/harness/components.json`은 구성 요소별로
필드는 다음과 같습니다.

```json
{
  "id": "HC-001",
  "path": "AGENTS.md",
  "profile": "core",
  "purpose": "Short routing entrypoint",
  "sources": ["SRC-CH-004", "SRC-REF-006", "SRC-ADV-003"],
  "applies_when": "Always",
  "validation": ["scripts/harness.py audit"],
  "review_trigger": "Router exceeds its signal budget or duplicates topic docs",
  "rollback": "Restore the previous validated component revision"
}
```

검증기는 다음을 확인합니다.

- 모든 source ID가 설치본 `docs/harness/source-map.json`의 65개 원장에 존재
- 모든 core 구성 파일이 존재
- Source 행의 연결 대상은 넓은 처분·영향 범위이고, Component의 `sources`는
  좁은 직접 근거라는 의미가 기계적으로 선언됨
- 모든 component→direct source가 해당 Source의 넓은 연결 대상에 포함되고,
  모든 `HC-*` 연결 대상이 실제 설치 구성 요소를 가리킴
- 기능 검증이 실제 gate에 연결되고 정확한 추적 파일이 존재
- 최신 `passing` 증거의 설정·검증·파일·revision·runtime이 현재 상태와 일치
- 모든 Source의 반영·통합·보류·참고 결정과 이유가 있음

## 구현 순서

1. Core 파일을 `template/core/`에 복제 가능한 형태로 분리 — 완료
2. 안전한 명령 배열과 validator 구현 — 완료
3. feature 상태 전환·증거 영수증 구현 — 완료
4. 빈 Fixture에서 콜드 스타트와 이중 실행 검증 — 완료
5. 기능 연결·신선도·runner·설치 경계·65개 Source·배포 수명주기 보강 — 완료
6. PowerShell 진입점·Windows process/path/receipt 어댑터 추가 — 완료
7. Standard 모듈 패키징 — 현재 `0.2.0` 범위 밖, 미래 릴리스의 명시적 재범위 필요
8. Advanced 모듈 패키징 — 현재 `0.2.0` 범위 밖, 병목·가치 증거와 명시적 재범위 필요

## 성능·유지보수

- 시작 경로는 네트워크 설치를 자동 실행하지 않고, `--setup`처럼 명시적
  모드에서만 의존성을 동기화하는 편이 빠르고 안전합니다.
- 빠른 검증과 전체 검증을 분리하되, 완료에 필요한 레벨을 낮추지 않습니다.
- 성공 출력은 짧게, 실패 출력은 실행 가능한 진단으로 만듭니다.
- runner는 stdout/stderr를 계속 drain하되 각 stream의 bounded tail만
  보관해 장시간·대출력 명령의 메모리 사용을 제한합니다.
- 기능별 `tracked_files`는 명시 비용이 있지만 전체 저장소 재해시보다
  결정적이고 변경 영향 범위가 작습니다.
- 상태 문서는 현재 사실만 유지하고, 내구 이력은 Git·완료 계획·결정 문서로
  이동합니다.
- 구성 요소마다 재검토 트리거를 두고 절제 실험으로 삭제 가능성을 확인합니다.

## 롤백·안전한 마이그레이션

- 초기 도입은 dry-run 뒤 제품 코드와 분리된 18개 하네스 파일만 추가합니다.
- 각 프로필은 독립 커밋으로 적용해 제거 가능하게 합니다.
- 업그레이드·제거는 설치 manifest가 소유권과 현재 digest를 증명하는
  파일만 변경하고, downgrade·호환되지 않는 버전을 거부하며, 쓰기 전
  `.harness/backups/`에 복구본을 둡니다.
- 파일 복사는 같은 디렉터리의 임시 파일을 완성한 뒤 원자적으로 노출하고,
  설치·추가 도중 실패하면 부분 파일과 새로 빈 디렉터리를 회수합니다.
- 양쪽이 바뀐 파일은 자동 덮어쓰지 않고 수동 병합 후 명시적
  `--accept-merged`로만 기준선을 전진시킵니다.
- validator를 CI 필수 게이트로 만들기 전 관찰 모드로 한 주기 실행합니다.
- 기존 상태 문서가 있으면 새 문서를 병렬로 늘리지 않고 필드를 매핑한 뒤
  하나의 canonical surface로 전환합니다.
- 자동 상태 전환은 영수증 이력을 남기며, 수동 복구 경로를 제공합니다.

## 과설계 방지 게이트

다음 질문에 `예`라고 답할 수 없으면 새 구성 요소를 Core에 넣지 않습니다.

1. 여러 프로젝트에서 반복되는 실제 실패를 막는가?
2. 해당 실패를 더 작은 기존 산출물이나 검사로 막을 수 없는가?
3. 채택·실행·제거 비용을 측정할 수 있는가?
4. 비활성 상태에서도 core startup을 깨뜨리지 않는가?
5. 제거 조건과 롤백 경로가 있는가?
