---
type: decision
title: Monday 읽기 전용 = 앱 계층 래퍼(MondayReadOnlyClient)로 mutation 차단
tags: [dwh, monday-com, readonly, security, port-adapter, etl]
status: active
---

# Monday 읽기 전용 = 앱 계층 래퍼(MondayReadOnlyClient)로 mutation 차단

## 결정

사내에서 발급받은 Monday.com API 토큰이 **read/write 모두 가능**하므로, 읽기 전용을 **우리 코드(래퍼)에서 강제**한다.

- 모든 Monday GraphQL 호출은 `MondayReadOnlyClient`를 통과한다.
- 래퍼가 GraphQL operation을 검사해 **mutation을 차단**하고 query만 전송한다. mutation이면 `ForbiddenWriteError`를 던진다.
- 상위 수집 코드에는 **쓰기 API 표면을 아예 노출하지 않는다** — 쓰기 메서드가 존재하지 않으므로 실수로도 호출 불가.

```python
class MondayReadOnlyClient:
    def execute(self, gql: str, variables: dict | None = None):
        if _contains_mutation(gql):          # 최상위 operation이 mutation이면 차단
            raise ForbiddenWriteError(gql)
        return self._transport.post(gql, variables)  # query만 전송
```

## 근거

- **토큰 권한으로는 강제 불가** — [[entity-monday-com]] 조사대로 Monday Personal V2 토큰은 UI 권한을 그대로 미러하고 **scope 축소가 불가능**하다. 발급 토큰이 read/write면 토큰 계층에서 읽기 전용을 만들 수 없다. OAuth read-scope 앱 토큰이 유일한 "권한적" 강제 수단이지만 현시점 전제되지 않는다.
- **최소 침습으로 즉시 안전** — 래퍼 한 겹이면 전 호출 경로를 덮는다. ETL은 본래 읽기만 하므로 mutation 차단이 기능을 해치지 않는다.
- **포트/어댑터 정합** — Monday 접근을 래퍼(포트) 뒤로 숨기면 향후 OAuth read-scope 토큰으로 교체 시 상위 코드 무변경 → [[concept-port-adapter]].
- **이중 방어로 확장 가능** — 나중에 OAuth read-scope 토큰을 도입하면 권한 계층 강제가 더해져, 래퍼(코드) + 토큰(권한) 이중 강제가 된다.

## 기각 대안

- **토큰 신뢰(강제 없음)** — "ETL이니 어차피 읽기만 한다" 가정. 코드 버그·오용 한 번으로 사내 Monday 데이터를 오염시킬 위험. read/write 토큰에서는 위험 과다.
- **정적 검사(CI/AST lint)만** — mutation 호출 코드가 커밋되지 못하게 막는 방식. 런타임 방어가 없어 동적 쿼리·문자열 조립을 놓칠 수 있다. 래퍼(런타임 차단)가 더 확실 — CI 검사는 보완책으로 추가 가능하나 필수 아님.
- **네트워크 계층 차단(프록시/방화벽)** — Monday는 read/write가 같은 엔드포인트(GraphQL 단일 URL)라 URL·메서드로 구분 불가. operation 본문을 봐야 하므로 애플리케이션 계층이 자연스러움.

## 관련

- [[entity-monday-com]] — 토큰 권한 모델(Personal V2 scope 축소 불가)의 원천
- [[concept-port-adapter]] — 래퍼 = Monday 접근 포트, 토큰 교체 = 어댑터 교체
- [[decision-monday-ingest-polling-only]] — 이 래퍼 위에서 폴링 레인이 동작(webhook 삭제)
- [[decision-monday-collector-langgraph-scheduled]] — 수집 에이전트가 이 래퍼를 통해서만 Monday 접근
- [[2026-07-10-dwh-monday-ingestion-refinements]] — 정정 논의 원본
