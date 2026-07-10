# DataWarehouse — Monday 적재·저장소 설계 정정 (2026-07-10)

> 2026-07-09 DataWarehouse 설계([[2026-07-09-dwh-design-plan]])에 대한 사용자 후속 지시.
> 인증 전제 정정 + 자동 수집·md 저장·DB 교체 가능성 요구를 확정한다. raw 불변 — 원문 그대로 보존.

## 사용자 지시 (원문)

> Entity에 mondays에서 발급해준 token은 읽기/쓰기 모두 가능한 API 토큰이어서 우리가 직접 레퍼로 읽기전용으로 만 설계해서 개발해야합니다. 이 부분도 스케줄러를 통해서 AI가 자동으로 데이터를 수집할 수 있도록 구성해야합니다. 관련된 내용을 md 포맷으로 저장할 수 있어야하고 md 저장을 위한 DB로 처음에 설계를 해야하고 앞으로 팀내 LLM WIKI를 개발할 것이기 때문에 이를 반영하여 DB를 언제든지 바꿔 낄 수 있도록 설계 되어야합니다.

## 확정 사항 (후속 질의 답변 반영)

### 1. Monday 토큰 = read/write → 앱 계층에서 읽기 전용 강제

- **정정 대상**: 2026-07-09 조사는 "personal 토큰은 읽기 전용 강제 불가, OAuth read scope만이 유일한 읽기 전용 강제 수단"이라 기록했다. 그러나 **실제 사내에서 발급받은 토큰은 read/write 모두 가능한 API 토큰**이다. OAuth read-scope 재발급이 (현시점) 전제되지 않으므로, **읽기 전용을 우리 코드(래퍼)에서 강제**해야 한다.
- **강제 수준(확정)**: **래퍼가 read-only 강제**. Monday GraphQL 클라이언트 래퍼(`MondayReadOnlyClient`)가 query만 허용하고 mutation 키워드를 코드/런타임에서 차단한다. 쓰기 API 표면을 상위 코드에 아예 노출하지 않는다.

```python
class MondayReadOnlyClient:
    def execute(self, gql: str, variables: dict | None = None):
        if _contains_mutation(gql):          # 'mutation' 최상위 operation 차단
            raise ForbiddenWriteError(gql)
        return self._transport.post(gql, variables)  # query만 전송
```
- 토큰 자체는 write 가능하므로 이는 "정책적/코드적" 강제이지 "권한적" 강제가 아니다 — 향후 OAuth read-scope 토큰으로 교체하면 권한 계층 강제가 이중화된다(더 안전). 지금은 래퍼 단일 강제.

### 2. 스케줄러를 통한 AI 자동 수집 (실행 방식 = LangGraph 에이전트 루프)

- Monday 데이터 수집을 사람이 돌리지 않고 **스케줄러가 트리거 → LangGraph 에이전트 루프가 수집·정리**하도록 구성한다.
- 스케줄러(cron/systemd timer, 향후 Airflow)는 시간 트리거만 담당하고, 실제 수집·md 변환은 LangGraph 에이전트가 수행하는 2층 구조.
- 이 결정은 기존 엔진 결정([[decision-engine-orchestration-langgraph]] · [[decision-model-provider-neutral-minimax]])과 정합 — 이미 생성 엔진을 LangGraph로 확정했으므로 수집 에이전트도 같은 런타임을 재사용한다.
- 야간 전수 폴링 시각·주기는 기존 [[decision-monday-ingest-hybrid]]의 02:00 KST 정책을 따른다. LangGraph 에이전트는 그 hybrid 적재의 "폴링 레인"을 구현하는 실행체다.

### 3. md 포맷 저장 + DB 교체 가능 설계 (팀 LLM WIKI 대비)

- 수집·정리된 내용은 **Markdown 포맷으로 저장**할 수 있어야 한다.
- md 저장을 위한 **DB를 처음부터 설계**하되, **DB를 언제든 갈아끼울 수 있도록** 추상화한다.
- **이유**: 앞으로 팀 내부 **LLM WIKI**를 개발할 것이므로, 초기 관계형 저장(PostgreSQL)에서 나중에 벡터 검색 저장(VectorStore) 등으로 backing store를 교체할 수 있어야 한다.
- **설계(확정)**: **`DocumentStore` 포트 인터페이스 + 어댑터**. md가 표준 산출/교환 포맷이고, 저장 백엔드는 어댑터로 교체한다.

```
interface DocumentStore:
    save(doc_md: str, meta: dict) -> id
    get(id) -> doc_md
    query(filter) -> [meta]

구현 어댑터:
    PostgresDocumentStore   # 지금 (control plane과 같은 PG 클러스터)
    FileDocumentStore       # 로컬/테스트
    VectorDocumentStore     # 향후 LLM WIKI (임베딩·유사도 검색)
```
- 상위 로직(수집 에이전트·조회)은 `DocumentStore` 포트에만 의존한다 → DB 교체 = 어댑터 교체. 이는 위키의 [[concept-port-adapter]] 패턴의 새 실체화다.
- **md ↔ DWH 관계**: md 문서는 사람이 읽는 산출/교환 포맷이자 LLM WIKI의 1급 자원이다. 이 md의 메타데이터(생성 이력·소스·품질)는 DWH의 `fact_item_documentation` 브릿지 팩트와 연결될 수 있으나, md 원문 저장의 SoT는 `DocumentStore`가 갖는다. (DWH gold 마트는 분석용, DocumentStore는 문서 원문·조회용 — 역할 분리.)

## 열린 항목

- DocumentStore의 초기 어댑터가 control plane PG와 **같은 스키마인지 별도 스키마/DB인지** — 지금은 같은 PG 클러스터의 별도 스키마로 가정(운영 시 확정).
- md 문서의 청킹·임베딩 정책은 LLM WIKI 착수 시점에 VectorDocumentStore 설계로 확정.
