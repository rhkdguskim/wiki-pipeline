import {ChevronDown, GitBranch, PlayCircle, Radio} from 'lucide-react';
import {StatusPill} from '../components/StatusPill.jsx';
import {EmptyState} from '../components/EmptyState.jsx';
import {PageHeader} from '../components/PageHeader.jsx';
import {OverviewNarrative} from '../components/OverviewNarrative.jsx';
import {StagesPage} from './StagesPage.jsx';
import {TracePage} from './TracePage.jsx';
import {STALL_SEC} from '../lib/format.js';

const SUB_TABS = [
  {id: 'overview', label: '개요'},
  {id: 'stages', label: '스테이지'},
  {id: 'feed', label: '트레이스', dev: true},
];

const STATUS_LABEL = {pending: '대기', running: '실행 중', done: '완료', failed: '실패'};

export function MonitorPage({
  runId, setRunId, filteredRuns, selectedSource, setSelectedSource, sources,
  S, live, state, stages, activeRun, runSummary,
  mrPlan, mrBusy, mrMessage, onSubmitMr,
  monitorView, setMonitorView, onOpenRepositories,
}) {
  return <div>
    <PageHeader
      title="모니터"
      description="선택한 run이 지금 무엇을 하고 있는지 보여줍니다"
      actions={<>
        <label className="selectWrap"><GitBranch size={15} /><select value={selectedSource} onChange={e => setSelectedSource(e.target.value)}>
          <option value="all">전체 소스</option>
          {sources.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select><ChevronDown size={14} /></label>
        <label className="selectWrap"><PlayCircle size={15} /><select value={runId} onChange={e => setRunId(e.target.value)}>
          <option value="">run 선택</option>
          {filteredRuns.map(r => <option key={r.run_id} value={r.run_id}>{r.run_id}{r.age_sec < STALL_SEC ? ' ●' : ''}</option>)}
        </select><ChevronDown size={14} /></label>
      </>}
    />

    {!runId ? (
      <>
        <EmptyState
          icon={Radio}
          title="이력에서 run을 선택하세요"
          description={filteredRuns.length ? '위 셀렉트 또는 아래 목록에서 run을 고르면 실행 상세가 표시됩니다' : '아직 실행 이력이 없습니다 — 저장소에서 소스를 실행하세요'}
          actionLabel={filteredRuns.length ? undefined : '저장소로 이동'}
          onAction={filteredRuns.length ? undefined : onOpenRepositories}
        />
        {!!filteredRuns.length && <section className="panel" style={{marginTop: 12}}>
          <div className="panelHead"><h2>최근 run</h2></div>
          <div className="tableScroll">
            <table>
              <thead><tr><th>run</th><th>소스</th><th>상태</th></tr></thead>
              <tbody>
                {filteredRuns.slice(0, 10).map(r => <tr key={r.run_id} className="clickable" onClick={() => setRunId(r.run_id)}>
                  <td className="mono strong ellipsis" title={r.run_id}>{r.run_id}</td>
                  <td className="ellipsis" title={r.source_id || ''}>{r.source_id || '-'}</td>
                  <td><span className={`stageState ${r.status || 'idle'}`}>{(r.status === 'running' || r.age_sec < STALL_SEC) && <span className="spinner tiny" />}{STATUS_LABEL[r.status] || r.status || (r.age_sec < STALL_SEC ? '실행 중' : '-')}</span></td>
                </tr>)}
              </tbody>
            </table>
          </div>
        </section>}
      </>
    ) : <>
      <div className="monitorHead">
        <StatusPill state={state} />
        <span className="contextTitle mono">{runId}</span>
        <span className="muted">{activeRun?.source_id || '-'}</span>
      </div>

      <nav className="tabs">
        {SUB_TABS.map(({id, label, dev}) => (
          <button key={id} className={monitorView === id ? 'active' : ''} onClick={() => setMonitorView(id)}>
            {label}{dev && <span className="devBadge">dev</span>}
          </button>
        ))}
      </nav>

      {monitorView === 'overview' && <OverviewNarrative
        S={S} live={live} state={state} stages={stages} activeRun={activeRun}
        runSummary={runSummary} mrPlan={mrPlan} mrBusy={mrBusy} mrMessage={mrMessage}
        onSubmitMr={onSubmitMr} onOpenTrace={() => setMonitorView('feed')}
      />}
      {monitorView === 'stages' && <StagesPage S={S} live={live} />}
      {monitorView === 'feed' && <TracePage S={S} live={live} state={state} stages={stages} />}
    </>}
  </div>;
}
