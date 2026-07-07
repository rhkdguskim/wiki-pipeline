import {
  AlertTriangle, ArrowRight, Bot, CheckCircle2, Clock3, Coins, Plus, Radio,
  Server, Sparkles, Workflow,
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

export function HomePage({sources, dbRuns, isLoading, isError, error, onRetry, onOpenWizard, onSelectRun, onOpenRepositories}) {
  if (isLoading) return <div><PageHeader title="Agent studio" description="운영 개요" /><LoadingBlock /></div>;
  if (isError) return <div><PageHeader title="Agent studio" description="운영 개요" /><ErrorBanner message={error?.message} onRetry={onRetry} /></div>;

  if (!sources.length) {
    return <div>
      <PageHeader title="Agent studio" description="저장소 연결" />
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
  const dayMs = 24 * 60 * 60 * 1000;
  const recent24h = dbRuns.filter(r => r.created_at && Date.now() - new Date(r.created_at).getTime() < dayMs);
  const failed24h = recent24h.filter(r => r.status === 'failed').length;
  const totalTokens = dbRuns.reduce((sum, r) => sum + (r.input_tokens || 0) + (r.output_tokens || 0), 0);
  const recentRuns = dbRuns.slice(0, 5);
  const runningRuns = dbRuns.filter(r => r.status === 'running').length;
  const done24h = recent24h.filter(r => r.status === 'done').length;
  const latestRun = dbRuns[0];
  const latestSource = sources.find(s => s.id === latestRun?.source_id);
  const successRate = recent24h.length ? Math.round((done24h / recent24h.length) * 100) : 0;

  return <div>
    <section className="agentHero">
      <div className="agentHeroCopy">
        <div className="eyebrow"><Sparkles size={14} />Agentic documentation control</div>
        <h1>Agent studio</h1>
        <p>저장소 변경을 읽고, 문서 갱신 run을 실행하고, 실패 지점을 바로 추적합니다.</p>
        <div className="heroActions">
          <button className="primaryBtn" onClick={onOpenWizard}><Plus size={15} />소스 추가</button>
          <button className="iconTextBtn" onClick={onOpenRepositories}>저장소 관리<ArrowRight size={15} /></button>
        </div>
      </div>

      <div className="agentConsole" aria-label="Agent status">
        <div className="consoleTop">
          <span><Bot size={15} />Studio AI</span>
          <span className={`consoleSignal ${runningRuns ? 'running' : 'ready'}`}>{runningRuns ? 'working' : 'ready'}</span>
        </div>
        <div className="consoleMessage agent">
          <span>Agent</span>
          <p>{latestRun ? `${latestSource?.label || latestRun.source_id || '선택된 소스'} run 상태를 확인했습니다.` : '아직 실행 이력이 없습니다.'}</p>
        </div>
        <div className="consoleMessage tool">
          <span>Tool call</span>
          <p>{recent24h.length} runs · {failed24h} failed · {fmtNum(totalTokens)} tokens</p>
        </div>
        <div className="consoleComposer">
          <span>Ask Agent Ops...</span>
          <button
            type="button"
            aria-label="최근 run 열기"
            onClick={() => latestRun && onSelectRun(latestRun.run_id)}
            disabled={!latestRun}
          >
            <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </section>

    <div className="agentMetricGrid">
      <div className="agentMetric">
        <span><Server size={15} />활성 소스</span>
        <strong>{activeSources}</strong>
        <small>전체 {sources.length}개</small>
      </div>
      <div className="agentMetric">
        <span><Radio size={15} />24시간 run</span>
        <strong>{recent24h.length}</strong>
        <small>{runningRuns ? `${runningRuns}개 실행 중` : '대기열 비어 있음'}</small>
      </div>
      <div className={failed24h ? 'agentMetric warn' : 'agentMetric good'}>
        <span>{failed24h ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}품질 신호</span>
        <strong>{recent24h.length ? `${successRate}%` : '-'}</strong>
        <small>{failed24h ? `${failed24h}건 확인 필요` : '최근 실패 없음'}</small>
      </div>
      <div className="agentMetric">
        <span><Coins size={15} />누적 토큰</span>
        <strong>{fmtNum(totalTokens)}</strong>
        <small>입력+출력 합계</small>
      </div>
    </div>

    <section className="agentWorkspace">
      <div className="panel agentPanel">
        <div className="panelHead">
          <h2><Workflow size={14} />Run queue</h2>
          <span>{runningRuns ? `${runningRuns} active` : 'idle'}</span>
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
        </div>
      </div>

      <div className="panel agentPanel">
        <div className="panelHead">
          <h2><Clock3 size={14} />Recent run</h2>
          <span>{recentRuns.length} items</span>
        </div>
        {recentRuns.length ? <div className="tableScroll">
          <table>
            <thead><tr><th>run</th><th>source</th><th>상태</th><th>시각</th></tr></thead>
            <tbody>
              {recentRuns.map(r => <tr key={r.run_id} className="clickable" onClick={() => onSelectRun(r.run_id)}>
                <td className="mono strong">{r.run_id}</td>
                <td>{r.source_id || '-'}</td>
                <td><span className={`stageState ${r.status || 'idle'}`}><span />{STATUS_LABEL[r.status] || r.status || '-'}</span></td>
                <td>{timeAgo(r.created_at)}</td>
              </tr>)}
            </tbody>
          </table>
        </div> : <EmptyState icon={Radio} title="아직 실행된 run이 없습니다" description="저장소 페이지에서 소스를 선택해 실행하세요" actionLabel="저장소로 이동" onAction={onOpenRepositories} />}
      </div>
    </section>
  </div>;
}
