import {
  Activity, AlertTriangle, CheckCircle2, Clock3, Coins, GitBranch, Plus, Radio,
  Server, Workflow,
} from 'lucide-react';
import {PageHeader} from '../components/PageHeader.jsx';
import {EmptyState} from '../components/EmptyState.jsx';
import {LoadingBlock, ErrorBanner} from '../components/QueryState.jsx';
import {fmtNum} from '../lib/format.js';

function timeAgo(iso) {
  if (!iso) return '-';
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return '방금';
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.round(hours / 24)}일 전`;
}

const STATUS_LABEL = {pending: '대기', running: '실행 중', done: '완료', failed: '실패'};

function aggregateSources(sources, runs) {
  const map = new Map(sources.map(s => [s.id, {
    source: s, total: 0, total24h: 0, done24h: 0, failed24h: 0, running: 0, tokens24h: 0, latest: null,
  }]));
  const now = Date.now();
  const dayMs = 24 * 60 * 60 * 1000;
  for (const r of runs) {
    if (!map.has(r.source_id)) {
      map.set(r.source_id, {source: {id: r.source_id, label: r.source_id || '-'}, total: 0, total24h: 0, done24h: 0, failed24h: 0, running: 0, tokens24h: 0, latest: null});
    }
    const st = map.get(r.source_id);
    const created = r.created_at ? new Date(r.created_at).getTime() : 0;
    st.total += 1;
    if (r.status === 'running') st.running += 1;
    if (created && now - created < dayMs) {
      st.total24h += 1;
      st.tokens24h += (r.input_tokens || 0) + (r.output_tokens || 0);
      if (r.status === 'done') st.done24h += 1;
      if (r.status === 'failed') st.failed24h += 1;
    }
    if (!st.latest || created > new Date(st.latest.created_at || 0).getTime()) st.latest = r;
  }
  return [...map.values()];
}

export function HomePage({sources, dbRuns, isLoading, isError, error, onRetry, onOpenWizard, onSelectRun, onOpenRepositories, onOpenPipelines}) {
  if (isLoading) return <div><PageHeader title="운영 현황" description="전체 상태" /><LoadingBlock /></div>;
  if (isError) return <div><PageHeader title="운영 현황" description="전체 상태" /><ErrorBanner message={error?.message} onRetry={onRetry} /></div>;

  if (!sources.length) {
    return <div>
      <PageHeader title="운영 현황" description="저장소 연결" />
      <EmptyState
        icon={Server}
        title="첫 저장소를 연결하세요"
        description="GitLab 또는 GitHub 저장소를 등록하면 문서 자동화 에이전트를 실행할 수 있습니다."
        actionLabel="+ 소스 추가"
        onAction={onOpenWizard}
      />
    </div>;
  }

  const activeSources = sources.filter(s => s.enabled).length;
  const disabledSources = sources.length - activeSources;
  const dayMs = 24 * 60 * 60 * 1000;
  const recent24h = dbRuns.filter(r => r.created_at && Date.now() - new Date(r.created_at).getTime() < dayMs);
  const failed24h = recent24h.filter(r => r.status === 'failed').length;
  const pendingRuns = dbRuns.filter(r => r.status === 'pending').length;
  const totalTokens = dbRuns.reduce((sum, r) => sum + (r.input_tokens || 0) + (r.output_tokens || 0), 0);
  const tokens24h = recent24h.reduce((sum, r) => sum + (r.input_tokens || 0) + (r.output_tokens || 0), 0);
  const recentRuns = dbRuns.slice(0, 8);
  const runningRuns = dbRuns.filter(r => r.status === 'running').length;
  const done24h = recent24h.filter(r => r.status === 'done').length;
  const latestRun = dbRuns[0];
  const latestSource = sources.find(s => s.id === latestRun?.source_id);
  const successRate = recent24h.length ? Math.round((done24h / recent24h.length) * 100) : null;
  const scheduledSources = sources.filter(s => (s.schedules || []).some(x => x.enabled) || s.schedule_cron).length;
  const scheduledPipelines = sources.reduce((sum, s) => sum + ((s.schedules || []).filter(x => x.enabled).length || (s.schedule_cron ? 1 : 0)), 0);
  const sourceStats = aggregateSources(sources, dbRuns)
    .sort((a, b) => (b.running - a.running) || (b.failed24h - a.failed24h) || (new Date(b.latest?.created_at || 0) - new Date(a.latest?.created_at || 0)));
  const attention = dbRuns.filter(r => r.status === 'failed' || r.status === 'running').slice(0, 6);
  const idleSources = sourceStats.filter(s => s.source.enabled && !s.latest).length;

  return <div>
    <PageHeader
      eyebrow="OPS"
      title="운영 현황"
      description="전체 저장소, 파이프라인 실행, 실패 신호, 토큰 사용량을 종합합니다"
      actions={<>
        <button className="primaryBtn" onClick={onOpenWizard}><Plus size={15} />소스 추가</button>
        <button className="iconTextBtn" onClick={onOpenPipelines}><Workflow size={15} />파이프라인</button>
      </>}
    />

    <section className="homeOpsBand">
      <div className="homeOpsPrimary">
        <div className="homeOpsSignal">
          <span className={`healthDot ${failed24h ? 'bad' : runningRuns ? '' : 'ok'}`} />
          <strong>{failed24h ? '확인 필요' : runningRuns ? '실행 중' : '정상'}</strong>
        </div>
        <p>{latestRun ? `${latestSource?.label || latestRun.source_id || '최근 소스'} · ${STATUS_LABEL[latestRun.status] || latestRun.status || '-'} · ${timeAgo(latestRun.created_at)}` : '아직 실행 이력이 없습니다.'}</p>
      </div>
      <div className="homeOpsFacts">
        <span><b>{runningRuns}</b> running</span>
        <span><b>{pendingRuns}</b> pending</span>
        <span><b>{failed24h}</b> failed 24h</span>
        <span><b>{idleSources}</b> idle sources</span>
      </div>
    </section>

    <div className="agentMetricGrid homeMetricGrid">
      <div className="agentMetric good">
        <span><Server size={15} />활성 소스</span>
        <strong>{activeSources}</strong>
        <small>전체 {sources.length}개 · 비활성 {disabledSources}</small>
      </div>
      <div className="agentMetric">
        <span><Radio size={15} />24시간 run</span>
        <strong>{recent24h.length}</strong>
        <small>{runningRuns ? `${runningRuns}개 실행 중` : '실행 중 없음'}</small>
      </div>
      <div className={failed24h ? 'agentMetric warn' : 'agentMetric good'}>
        <span>{failed24h ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}품질 신호</span>
        <strong>{successRate == null ? '-' : `${successRate}%`}</strong>
        <small>{failed24h ? `${failed24h}건 확인 필요` : '최근 실패 없음'}</small>
      </div>
      <div className="agentMetric">
        <span><Workflow size={15} />스케줄</span>
        <strong>{scheduledPipelines}</strong>
        <small>{scheduledSources}개 소스에 활성화</small>
      </div>
      <div className="agentMetric">
        <span><Coins size={15} />24시간 토큰</span>
        <strong>{fmtNum(tokens24h)}</strong>
        <small>누적 {fmtNum(totalTokens)}</small>
      </div>
    </div>

    <section className="homeMainGrid">
      <div className="panel">
        <div className="panelHead">
          <h2><Activity size={14} />실시간 작업</h2>
          <span>{attention.length} items</span>
        </div>
        {attention.length ? <div className="homeAttentionList">
          {attention.map(r => <button type="button" key={r.run_id} className={`homeAttentionItem ${r.status || ''}`} onClick={() => onSelectRun(r.run_id)}>
            <span className={`pill small ${r.status || ''}`}>{STATUS_LABEL[r.status] || r.status || '-'}</span>
            <strong className="mono">{r.run_id}</strong>
            <small>{r.source_id || '-'} · {timeAgo(r.created_at)}</small>
          </button>)}
        </div> : <div className="emptyPanel compact">진행 중이거나 실패한 run이 없습니다</div>}
      </div>

      <div className="panel">
        <div className="panelHead">
          <h2><GitBranch size={14} />저장소 상태</h2>
          <span>{sourceStats.length} sources</span>
        </div>
        <div className="homeSourceList">
          {sourceStats.slice(0, 7).map(st => {
            const s = st.source;
            const status = st.latest?.status;
            return <button type="button" key={s.id} className="homeSourceRow" onClick={() => st.latest ? onSelectRun(st.latest.run_id) : onOpenRepositories()}>
              <span className={`stageState ${st.running ? 'running' : status === 'failed' ? 'failed' : s.enabled ? 'done' : 'idle'}`}><span />{st.running ? '실행 중' : status === 'failed' ? '실패' : s.enabled ? '활성' : '비활성'}</span>
              <strong>{s.label || s.id}</strong>
              <small>{st.total24h} runs · {st.failed24h} failed · {timeAgo(st.latest?.created_at)}</small>
            </button>;
          })}
        </div>
      </div>
    </section>

    <section className="agentWorkspace homeRunGrid">
      <div className="panel agentPanel">
        <div className="panelHead">
          <h2><Workflow size={14} />최근 실행</h2>
          <span>{latestRun ? STATUS_LABEL[latestRun.status] || latestRun.status : 'none'}</span>
        </div>
        <div className="runStrip">
          <div>
            <span>Latest</span>
            <strong className="mono">{latestRun?.run_id || '-'}</strong>
          </div>
          <div>
            <span>Source</span>
            <strong>{latestSource?.label || latestRun?.source_id || '-'}</strong>
          </div>
          <div>
            <span>Updated</span>
            <strong>{timeAgo(latestRun?.created_at)}</strong>
          </div>
          <div>
            <span><Coins size={15} />누적 토큰</span>
            <strong>{fmtNum(totalTokens)}</strong>
          </div>
        </div>
      </div>

      <div className="panel agentPanel">
        <div className="panelHead">
          <h2><Clock3 size={14} />Run history</h2>
          <span>{recentRuns.length} items</span>
        </div>
        {recentRuns.length ? <div className="tableScroll">
          <table>
            <thead><tr><th>run</th><th>source</th><th>상태</th><th>시각</th></tr></thead>
            <tbody>
              {recentRuns.map(r => <tr key={r.run_id} className="clickable" onClick={() => onSelectRun(r.run_id)}>
                <td className="mono strong">{r.run_id}</td>
                <td>{r.source_id || '-'}</td>
                <td><span className={`pill small ${r.status || ''}`}>{STATUS_LABEL[r.status] || r.status || '-'}</span></td>
                <td>{timeAgo(r.created_at)}</td>
              </tr>)}
            </tbody>
          </table>
        </div> : <EmptyState icon={Radio} title="아직 실행된 run이 없습니다" description="저장소 페이지에서 소스를 선택해 실행하세요" actionLabel="저장소로 이동" onAction={onOpenRepositories} />}
      </div>
    </section>
  </div>;
}
