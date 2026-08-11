# Current State

## 목표

Core `0.4.0`의 요청형 다중 에이전트 안전 계약(`HST-016`)과 상주 에이전트의
컨텍스트·검증 비용 상한(`HST-017`)을 완료하고, 설치 Core의 유한한 실행 계약과
스타터 원본의 빠른 시작·전체 완료 게이트를 함께 유지합니다.

## 현재 검증된 상태

- 원본 학습 폴더는 읽기 전용이며, 내장 원장은 65개 Source의 경로·크기·
  SHA-256 접두사와 65행 처분 결정을 보존합니다.
- Core `0.4.0`은 22개 관리 파일입니다. `docs/AGENT_COORDINATION.md`는
  `HC-022`로 등록되고 `SRC-CH-007..009`, `SRC-TPL-001`, `SRC-TPL-006`,
  `SRC-TPL-010`, `SRC-PRJ-004`, `SRC-PRJ-006`에 양방향 연결됩니다.
- `AGENTS.md`는 `harness:agent-coordination:v1` 표식과 온디맨드 경로만
  보유하고 `CLAUDE.md`는 `@AGENTS.md`를 import합니다. provider별 팀 생성,
  claim, lease, 메시징 또는 잠금 구현은 설치하지 않습니다.
- 병렬 쓰기는 사용자의 명시적 요청, 공통의 깨끗한 Git revision, writer별
  worktree, 비중첩 소유권과 격리된 공유 상태가 있을 때만 허용됩니다. 그 조건을
  만족하지 않으면 읽기만 병렬화하고 쓰기는 직렬화합니다.
- worker는 상태·영수증·통합 checkout을 갱신하지 않습니다. lead가 실제
  base/head·diff·변경 경로를 확인해 의존성 순서로 한 결과씩 통합하고, 집중
  검사와 전체 위험 gate를 다시 실행합니다. `cross_component`와 `high_risk`는
  별도의 read-only reviewer가 필요합니다.
- 요청형 병렬 실행의 기본 예산은 worker 2명, 위임 깊이 0, round 2회,
  review cycle 1회이며 deadline·worker timeout·전달 context·token 또는
  `unavailable` 표식·8 KiB 인계·cleanup 시점을 시작 전에 확정합니다.
- 상시 읽기 문서는 Core `AGENTS.md` 7,041바이트, `CLAUDE.md` 11바이트,
  `STATE.md` 605바이트로 합계 7,657바이트입니다. 조건부
  `COMMUNICATION.md` 11,741바이트와 `AGENT_COORDINATION.md` 10,077바이트는
  해당 요청에서만 읽습니다.
- 일반 `init`은 repository audit를 한 번만 수행하고 같은 프로세스에서 bounded
  cold-start 요약을 반환합니다. `--setup`은 변경 전후 경계를 증명하기 위해
  두 번 audit하며, repository identity stack이 같은 Core의 직·간접 재진입을
  거부하면서 서로 다른 Core의 연쇄 호출은 허용합니다.
- gate는 `profile`과 `feature` 실행 범위를 구분합니다. 시작·일반 verify는
  profile command만 실행하고 완료는 profile command와 현재 기능이 bind한
  feature command만 실행합니다. 선택 레벨에 profile command가 없으면
  통과를 주장하지 않습니다.
- receipt 신선도는 실행 계약 버전 2와 유효 기본값을 포함합니다. Git ancestry는
  감사당 10초, Source 확장 edge는 기능당 128개, 고유 receipt 입력은 64 MiB,
  고유 tracked input은 256 MiB로 제한되며 파일 성장과 비표준 `NaN`·`Infinity`
  우회도 거부합니다.
- runner는 실행 전 command 수·timeout 합·combined output을 검사하고 각
  command의 bounded tail만 보관합니다. timeout과 정상 종료 뒤 남은 descendant
  모두 process tree 단위로 정리하며 pipe를 잡은 자식이 남으면 성공으로
  처리하지 않습니다.
- clean-state 검사는 symlink를 따라가지 않는 streaming 순회로 최대 250,000개
  entry만 처리하고 읽을 수 없는 subtree와 제한 초과를 `WHAT / WHY / FIX`로
  실패시킵니다.
- root `init.ps1 -Quick`과 `init.sh --quick`는 bounded source/Core 순회와
  watchdog이 적용된 template self-audit까지만 실행합니다. 인자 없는 기존
  adapter는 전체 distribution Fixture를 계속 기본·완료 게이트로 실행합니다.
- Windows Quick은 필수 산출물 38/38, Source 65/65, 상태·WIP·증거와 copy-ready
  Core 검사를 1.838초에 통과했습니다. 변경 전 인자 없는 전체 기준선은
  83.4초였으므로 시작 경로만 약 45배 짧아졌고 전체 검증 의미는 유지됩니다.
- 인자 없는 Windows `init.ps1` 완료 기준선은 96.222초에 exit 0으로 끝났습니다.
  전체 Fixture 54개는 94.254초 동안 52개가 통과하고 POSIX `sh`와 Node 미설치
  조건 2개가 명시적으로 skip되었습니다.
- 독립 read-only 검토는 최종 코드에서 남은 P1/P2 문제를 찾지 못했습니다.
  현재 프로젝트는 로컬 `main`이며 커밋·푸시는 요청받지 않았습니다.

## 이번 단계의 결정

- Git 기준선과 공개 릴리스는 여전히 `0.3.0`이므로 `HST-016`과 `HST-017`은
  같은 미출시 Core `0.4.0` minor에 포함합니다. 새 hard limit을
  backward-compatible `0.4.1` patch라고 주장하지 않습니다.
- `0.3.x → 0.4.x` 자동 업그레이드는 거부합니다. 22개 관리 파일을 검토해
  수동 병합하고 audit·플랫폼 init·영향 gate를 재실행한 뒤 manifest 기준선을
  전진합니다.
- 기능 WIP=1, `feature_list.json` 상태 기계, receipt schema와 기존 상태 CLI는
  유지합니다. `execution_scope`와 runner aggregate budget은 기본값이 있는
  실행 계약 필드이며 root Quick은 스타터 원본 adapter의 명시적 옵션입니다.
- worker 메시지와 성공 주장은 참고 정보일 뿐 완료 증거가 아닙니다. lead가
  보존된 결과를 확인하고 직접 재실행한 명령과 기존 receipt만 최종 증거입니다.

## 열린 위험

- 저장소 계약은 상위 host의 더 높은 우선순위 위임 정책을 강제하거나 실제
  provider token 사용량을 증명하지 못합니다. Codex·Claude의 클라이언트·모델·
  런타임 변경 시 깨끗한 복제본에서 단일-agent와 명시적 병렬 smoke trace를
  별도로 확인해야 합니다.
- Core는 Python 3.10+와 로컬 regular-file 의미를 요구합니다. UNC·네트워크
  파일시스템, provider-managed reparse point, 제품별 공유 DB·포트·캐시 격리는
  채택 프로젝트가 별도로 검증합니다.
- 실행 상한은 유한한 안전 기본값입니다. 더 큰 프로젝트는 허용 범위를 무제한으로
  풀지 않고 측정된 command·receipt·tracked-file 비용에 근거해 조정해야 합니다.
- 실제 제품 E2E 품질은 채택 프로젝트가 올바른 risk profile, gate binding과
  tracked file을 구성하고 최종 gate를 다시 실행해야 확보됩니다.

## 다음 행동

- active 기능은 없습니다. 클라이언트·런타임 변경 또는 Core `0.4.0` 채택 시
  깨끗한 복제본 smoke와 수동 migration 검토를 실행합니다.
