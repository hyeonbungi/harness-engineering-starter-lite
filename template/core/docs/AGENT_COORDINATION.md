<!-- harness:agent-coordination:v1 -->
# 복수 에이전트 조정 계약

이 문서는 사용자가 복수 에이전트 또는 병렬 작업을 명시적으로 요청했을 때만
읽습니다. 일반 작업에서 에이전트를 자동으로 생성하지 않습니다. 이 계약은
호스트가 제공하는 병렬 실행을 안전하게 사용하는 규칙이며, 팀 생성·메시징·
작업 claim·lease·프로세스 잠금을 구현하는 오케스트레이터가 아닙니다.

## 1. 병렬화 여부

lead는 에이전트를 만들기 전에 작업을 독립적인 단위로 나눌 수 있는지
확인합니다. 다음 조건을 모두 만족하는 작업만 동시에 실행합니다.

- 각 작업의 목표, 입력, 결과물과 종료 조건이 분명합니다.
- 작업 사이에 순서 의존성이 없습니다.
- 파일과 상태 소유권이 겹치지 않습니다.
- 공용 DB, 포트, 캐시나 외부 시스템을 함께 변경하지 않습니다.
- 병렬화 이점이 조정·검토 비용보다 큽니다.

순차 단계, 같은 파일 수정, 하나의 migration·lockfile·생성 산출물·전역 설정을
함께 바꾸는 작업은 한 worker에게 맡기거나 직렬 처리합니다.

## 2. 공통 기준선과 역할

lead는 writer를 시작하기 전에 공통의 깨끗한 Git 기준 revision을 기록합니다.
필요한 제품 변경이 아직 commit되지 않았다면 병렬 쓰기를 시작하지 않고,
읽기 작업만 병렬화하거나 사용자가 허용한 체크포인트를 먼저 만듭니다.

- **lead**: 작업 분해, 권한·소유권 배정, 진행 확인, 직렬 통합, 최종 검증과
  상태·증거 갱신의 유일한 책임자입니다.
- **worker**: 배정된 worktree와 소유 경로 안에서 한 작업만 수행하고 구조화된
  인계를 반환합니다.
- **reviewer**: 통합본을 읽기 전용으로 검사하며 직접 수정하지 않습니다.

전역 WIP는 계속 1입니다. 모든 worker는 하나의 active 기능에 속한 하위
작업입니다. `feature_list.json`, `docs/STATE.md`, 완료 영수증과 통합 브랜치는
lead만 갱신합니다. worker는 `activate`, `reopen`, `block`, `complete` 상태
명령을 실행하지 않습니다.

## 3. 유한한 실행 예산

lead는 병렬 적합성을 판단한 뒤, worker를 만들기 전에 다음 예산을 한 번
확정합니다. 사용자가 더 작은 값을 정하면 그 값을 따르며 기본값을 넘기려면
측정된 이점과 사용자의 명시적 요청이 모두 필요합니다.

```yaml
parallel_budget:
  max_parallel_workers: 2
  max_worker_rounds: 2
  max_review_cycles: 1
  max_delegation_depth: 0
  timeout_minutes: 양의 정수
  token_budget: 양의 정수 | unavailable
  context_mode: minimal
  handoff_max_bytes: 8192
  enforcement: host | advisory
```

- lead는 가장 작은 worker 수를 사용하며 동시에 실행하는 worker는 최대
  2명입니다. 최초 배정과 follow-up을 합쳐 worker별 최대 2 round입니다.
- worker는 하위 에이전트를 생성하지 않습니다. `max_delegation_depth: 0`을
  강제할 수 없는 호스트에서는 writer를 병렬 실행하지 않고 읽기만 병렬화합니다.
- `context_mode: minimal`은 공통 기준 revision, 이 문서, 배정 레코드와 관련
  파일만 전달한다는 뜻입니다. 전체 대화 fork만 가능한 호스트에서는
  `enforcement: advisory`로 기록하고 worker 수를 1로 낮춥니다.
- lead는 절대 deadline까지 기다리고 timeout worker를 `blocked` 또는 `failed`로
  인계합니다. 예산 소진은 완료가 아니며 새 round를 시작하지 않습니다.
- 실제 token을 계량할 수 없으면 `token_budget: unavailable`로 기록하고 유한한
  worker·round·timeout·handoff 예산을 강제합니다. 토큰 계량이 가능하면 모든
  worker와 reviewer의 합계를 같은 예산에 포함합니다.
- reviewer는 writer 통합 뒤 직렬로 시작하고 최대 1회 review cycle만 수행합니다.
  finding 수정 뒤 필요한 검토와 gate를 다시 실행하되 새 cycle이 필요하면
  lead가 작업을 멈추고 남은 위험을 보고합니다.
- 보존 전에는 작업 공간을 정리하지 않습니다. 보존·통합 뒤 lead만 브랜치와
  worktree를 정리하며, 남은 worktree 수는 `max_parallel_workers`를 넘기지 않고
  정리하지 못한 항목을 최종 인계에 기록합니다.

## 4. 작업 배정

lead는 각 worker에게 다음 필드를 빠짐없이 전달합니다.

```yaml
task_id: stable-subtask-id
objective: 관찰 가능한 결과
base_revision: 공통 Git commit
dependencies: []
mode: read-only | writer
assigned_paths: []
forbidden_paths:
  - feature_list.json
  - docs/STATE.md
  - .harness/evidence/
validation_commands: []
risk_profile: docs_only | local_code | runtime_change | cross_component | high_risk
deliverable: diff 또는 근거가 있는 조사 결과
stop_conditions: []
```

writer의 소유 경로는 서로 겹치지 않아야 합니다. 경로 목록만 달라도 같은
lockfile, migration 순서, 코드 생성기, DB schema, 포트나 캐시를 공유하면
독립 작업이 아닙니다. lead는 자원별 고유 namespace를 배정하거나 해당 작업을
직렬화합니다.

## 5. 격리와 실행

- writer마다 별도 worktree와 고유 브랜치 또는 보존 가능한 detached 작업
  공간을 사용합니다. 다른 writer와 같은 checkout에서 동시에 쓰지 않습니다.
- Git/worktree에 준하는 격리를 만들 수 없으면 병렬 쓰기를 금지하고, 변경은
  한 에이전트가 직렬 수행합니다.
- 같은 checkout의 병렬 읽기는 tracked file, 외부 상태와 공용 실행 자원을
  바꾸지 않는 명령에만 허용합니다. 테스트가 캐시·DB·포트를 공유하면 격리하거나
  직렬화합니다.
- worker는 다른 브랜치를 merge·rebase하거나 다른 worktree를 정리하지
  않습니다. commit·push도 현재 사용자 권한과 저장소 정책이 허용할 때만
  수행합니다.
- worker는 작업 전후의 기준 revision과 변경 파일을 확인합니다.

비 Git 프로젝트, 겹치는 파일 범위, 공유 상태 격리를 정의하지 않은 배정은
병렬 writer 사용 중지 조건입니다. 필요한 읽기 작업만 병렬화하고 쓰기는
lead가 직렬 처리합니다.

예상하지 못한 dirty 파일, 소유권 중첩, 기준 revision 불일치, 실패한 검사,
권한 밖 변경, 미확인 요구사항이 발견되면 즉시 멈추고 lead에게 반환합니다.
임의로 범위를 넓히거나 다른 worker의 변경을 고치지 않습니다.

## 6. worker 인계

worker는 자유 형식의 성공 선언 대신 다음 구조를 그대로 채웁니다.

```yaml
task_id: stable-subtask-id
status: completed | blocked | failed
base_revision: 시작 commit
result_revision: 결과 commit 또는 null
worktree_or_diff: 보존된 worktree 또는 diff 위치
assigned_paths: []
changed_paths: []
summary: 수행 결과
validation:
  - command: 정확히 실행한 명령
    exit_code: 0
    result: 핵심 결과
not_run: []
assumptions: []
unknowns: []
failures_or_conflicts: []
remaining_risks: []
integration_order: 권장 순서와 이유
```

worker의 `status`는 하위 작업 결과만 뜻합니다. `passing`이나 기능의 최종
완료를 주장하지 않습니다. 실행하지 않은 검사는 `not_run`에 기록하고,
검증 결과를 추측하거나 실패를 숨기지 않습니다. 인계 전체는
`handoff_max_bytes: 8192` 이하로 유지하고 긴 로그 대신 보존 위치와 핵심 결과를
기록합니다.

## 7. lead 통합과 완료 증거

lead는 배정한 deadline 안에서 모든 worker의 반환을 기다립니다. 중단·실패·
timeout·누락된 worker를 완료로 간주하지 않습니다. 인계 설명만 믿지 않고 다음
순서로 통합합니다.

1. `base_revision`, 실제 diff와 `changed_paths`가 배정과 일치하는지 확인합니다.
2. 의존성 순서대로 한 결과씩 통합하고 충돌은 lead가 한 곳에서 해결합니다.
3. 각 통합 뒤 관련 집중 검사를 실행합니다.
4. 전체 통합 뒤 선택한 위험 프로필의 모든 gate를 lead가 직접 다시 실행합니다.
5. 성공한 현재 영수증이 만들어진 뒤에만 상태와 완료를 보고합니다.
6. 결과가 commit, 통합 또는 명시적으로 보존되기 전에는 worktree나 브랜치를
   삭제하지 않습니다.

에이전트 간 메시지와 `테스트 통과` 주장은 참고 정보일 뿐 완료 증거가
아닙니다. lead가 확인한 파일·diff와 직접 다시 실행한 명령, 기존 완료 영수증만
최종 증거로 사용합니다.

## 8. 위험 기반 독립 검토

`cross_component`와 `high_risk` 통합본은 작성에 참여하지 않은 별도의
read-only reviewer가 검토해야 합니다. reviewer는 요구사항 누락, 파일 간
충돌, 보안·복구 위험과 테스트 공백을 파일 위치와 실행 근거로 보고하고 직접
수정하지 않습니다.

finding이 있으면 lead가 writer에게 제한된 수정 작업을 다시 배정하거나 직접
통합 결정을 내리고, 영향을 받은 검토와 전체 gate를 재실행합니다. 그보다 낮은
위험은 lead의 실제 diff 확인과 재검증으로 충분합니다.

## 9. 보장 경계

정적 audit는 계약이 설치되어 있고 핵심 문구가 유지되는지만 증명합니다.
특정 Codex·Claude 버전이 규칙을 의미적으로 따르거나 호스트가 실제 worktree
격리와 권한을 강제하는지는 증명하지 않습니다. 클라이언트·모델·런타임이
바뀌면 깨끗한 복제본에서 병렬 smoke test를 다시 수행하고, 확인하지 못한
동작은 `미확인`으로 보고합니다. 실제 token 계량, 동시 worker 수, 부모-자식
관계, round, deadline 중단과 예산 소진 뒤 추가 배정이 없었다는 사실은 저장소
문구가 아니라 호스트 실행 기록으로 검증합니다.
