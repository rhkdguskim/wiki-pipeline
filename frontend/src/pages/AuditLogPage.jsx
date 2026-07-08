import {useState} from 'react';
import {Shield} from 'lucide-react';
import {PageHeader} from '../components/PageHeader.jsx';
import {ErrorBanner, LoadingBlock} from '../components/QueryState.jsx';
import {useAuditRecentQuery} from '../hooks/queries.js';
import {fmtClock} from '../lib/format.js';

const ACTION_LABELS = {
  'source.create': '소스 생성',
  'source.update': '소스 갱신',
  'instance.create': 'SCM 인스턴스 생성',
  'instance.update': 'SCM 인스턴스 갱신',
  'doc_target.create': 'docs-hub 대상 생성',
  'doc_target.update': 'docs-hub 대상 갱신',
};

const TARGET_LABEL = {
  source: '소스',
  scm_instance: 'SCM 인스턴스',
  doc_target: 'docs-hub 대상',
};

const KNOWN_ACTIONS = [
  '', 'source.create', 'source.update',
  'instance.create', 'instance.update',
  'doc_target.create', 'doc_target.update',
];

function fmtTs(iso) {
  if (!iso) return '-';
  return fmtClock(Date.parse(iso));
}

function actionLabel(a) {
  return ACTION_LABELS[a] || a || '-';
}

function targetLabel(kind, id) {
  const prefix = TARGET_LABEL[kind] || (kind || '대상');
  return id ? `${prefix} · ${id}` : prefix;
}

export function AuditLogPage({isAdmin}) {
  const [action, setAction] = useState('');
  const [actor, setActor] = useState('');
  const [limit, setLimit] = useState(100);

  const auditQuery = useAuditRecentQuery({action, actor, limit});
  const entries = auditQuery.data?.entries || [];

  return <div>
    <PageHeader
      eyebrow="ADMIN"
      title="감사 로그"
      description="관리 mutation 의 시점·대상·행위자. 감사 추적 (ENT-F) — 토큰 평문은 기록하지 않습니다."
      actions={
        isAdmin ? null : (
          <span className="pill small" title="관리자 토큰 필요">읽기 전용</span>
        )
      }
    />

    <section className="panel" style={{marginBottom: 12}}>
      <div className="auditFilters">
        <label className="auditField">
          <span>액션</span>
          <select value={action} onChange={e => setAction(e.target.value)}>
            {KNOWN_ACTIONS.map(a => (
              <option key={a || 'all'} value={a}>
                {a ? actionLabel(a) : '전체'}
              </option>
            ))}
          </select>
        </label>
        <label className="auditField">
          <span>행위자 (토큰 이름)</span>
          <input
            type="text"
            value={actor}
            onChange={e => setActor(e.target.value)}
            placeholder="예: prod-bot, dev-token"
          />
        </label>
        <label className="auditField" style={{maxWidth: 120}}>
          <span>개수</span>
          <select value={limit} onChange={e => setLimit(Number(e.target.value))}>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={200}>200</option>
            <option value={500}>500</option>
          </select>
        </label>
        <button
          type="button"
          className="ghostBtn"
          onClick={() => { setAction(''); setActor(''); setLimit(100); }}
        >
          초기화
        </button>
      </div>
    </section>

    {auditQuery.isLoading && <LoadingBlock />}
    {auditQuery.isError && <ErrorBanner message={auditQuery.error?.message} onRetry={() => auditQuery.refetch()} />}

    {!auditQuery.isLoading && !auditQuery.isError && !entries.length && (
      <section className="panel">
        <div className="emptyPanel">
          <strong>감사 기록 없음</strong>
          <p className="muted">필터를 초기화하거나 잠시 후 다시 시도하세요.</p>
        </div>
      </section>
    )}

    {entries.length > 0 && (
      <section className="panel">
        <div className="panelHead">
          <h2><Shield size={14} /> 최근 감사 ({entries.length}건)</h2>
          <span className="coordTag">{auditQuery.data?.limit || limit} LIMIT</span>
        </div>
        <div className="tableScroll">
          <table className="auditTable">
            <thead>
              <tr>
                <th>시각</th>
                <th>액션</th>
                <th>대상</th>
                <th>행위자</th>
                <th>상세</th>
                <th>요청 ID</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.id}>
                  <td className="mono" title={e.ts}>{fmtTs(e.ts)}</td>
                  <td><span className="pill small">{actionLabel(e.action)}</span></td>
                  <td className="ellipsis" title={`${e.target_kind} · ${e.target_id}`}>
                    {targetLabel(e.target_kind, e.target_id)}
                  </td>
                  <td className="mono">{e.actor || '-'}</td>
                  <td className="auditDetail mono" title={e.detail}>{e.detail || '-'}</td>
                  <td className="mono" style={{fontSize: 11, color: 'var(--muted)'}}>
                    {e.request_id ? e.request_id.slice(0, 12) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    )}
  </div>;
}
