import {Activity, CheckCircle2, Clock3, History, Server} from 'lucide-react';
import {PageHeader} from '../components/PageHeader.jsx';
import {RunsTable} from '../components/RunsTable.jsx';
import {ErrorBanner, LoadingBlock} from '../components/QueryState.jsx';
import {usePipelineStatusQuery} from '../hooks/queries.js';
import {fmtClock, fmtDur, fmtNum, nf} from '../lib/format.js';
import {MonitorPage} from './MonitorPage.jsx';

const STATUS_PILL = {pending: '대기', running: '실행 중', done: '완료', failed: '실패'};
const PIPELINE_LABEL = {static: '정적', manual: '매뉴얼'};
const PIPELINE_WINDOW_HOURS = 24;

function fmtRelative(iso) {
  if (!iso) return '-';
  const ms = Date.now() - Date.parse(iso);
  if (!Number.isFinite(ms) || ms < 0) return fmtClock(Date.parse(iso));
  if (ms < 60000) return '방금';
  if (ms < 3600000) return `${Math.floor(ms / 60000)}분 전`;
  if (ms < 86400000) return `${Math.floor(ms / 3600000)}시간 전`;
  return `${Math.floor(ms / 86400000)}일 전`;
}

function fmtErrKind(kind) {
  if (!kind) return '';
  if (kind === 'not_found') return '404';
  if (kind === 'auth') return '인증';
  if (kind === 'rate_limited') return 'rate limit';
  return kind;
}

export function PipelineStatusPage({
  onOpenSource, onOpenRun, onTrigger,
  dbRuns = [], dbRunsIsLoading = false, dbRunsIsError = false, dbRunsError = null,
  onRetryDbRuns, sources = [],
  runId, setRunId, filteredRuns, selectedSource, setSelectedSource,
  S, live, state, stages, activeRun, runSummary,
  mrPlan, mrBusy, mrMessage, onSubmitMr,
  monitorView, setMonitorView, onOpenRepositories,
}) {
  const windowHours = PIPELINE_WINDOW_HOURS;
  const psQuery = usePipelineStatusQuery(windowHours);
  const pipelines = psQuery.data?.pipelines || [];
  const generatedAt = psQuery.data?.generated_at;

  if (runId) {
    return <MonitorPage
      runId={runId}
      setRunId={setRunId}
      filteredRuns={filteredRuns}
      dbRuns={dbRuns}
      selectedSource={selectedSource}
      setSelectedSource={setSelectedSource}
      sources={sources}
      S={S}
      live={live}
      state={state}
      stages={stages}
      activeRun={activeRun}
      runSummary={runSummary}
      mrPlan={mrPlan}
      mrBusy={mrBusy}
      mrMessage={mrMessage}
      onSubmitMr={onSubmitMr}
      monitorView={monitorView}
      setMonitorView={setMonitorView}
      onOpenRepositories={onOpenRepositories}
      title="파이프라인"
      eyebrow={`RUN · ${runId.slice(0, 12)}`}
      description="선택한 run의 실시간 진행 흐름과 산출물 상태"
    />;
  }

  // aggregate
  const totals = {
    pipelines: pipelines.length,
    success: 0, failed: 0, running: 0,
    tokens: 0, withSchedule: 0,
  };
  for (const p of pipelines) {
    totals.success += p.success_window || 0;
    totals.failed += p.failed_window || 0;
    totals.running += p.running || 0;
    totals.tokens += p.total_tokens_window || 0;
    if (p.enabled_schedule) totals.withSchedule += 1;
  }
  const totalWindow = totals.success + totals.failed + totals.running;
  const successRate = totalWindow ? Math.round((totals.success / totalWindow) * 100) : null;

  return <div>
    <PageHeader
      eyebrow="PIPELINES"
      title="파이프라인"
      description="소스별 파이프라인 헬스와 최근 실행 이력을 한 화면에서 확인합니다"
    />

    <section className="stats">
      <Kpi icon={Server} label="파이프라인" value={String(totals.pipelines)}
            hint={`스케줄 활성 ${totals.withSchedule}개`} />
      <Kpi icon={Activity} label={`${windowHours}H 성공`} value={String(totals.success)}
            hint={`실패 ${totals.failed} · 실행 중 ${totals.running}`}
            warn={totals.failed > 0} />
      <Kpi icon={CheckCircle2} label="성공률"
            value={successRate == null ? '-' : `${successRate}%`}
            hint={totalWindow ? `${totals.success}/${totalWindow}` : '데이터 없음'}
            good={successRate != null && successRate >= 80} />
      <Kpi icon={Clock3} label={`${windowHours}H 토큰`} value={fmtNum(totals.tokens)}
            hint="입력+출력 합계" />
    </section>

    {psQuery.isLoading && <LoadingBlock />}
    {psQuery.isError && <ErrorBanner message={psQuery.error?.message} onRetry={() => psQuery.refetch()} />}

    {!psQuery.isLoading && !psQuery.isError && !pipelines.length && (
      <section className="panel">
        <div className="emptyPanel">
          <strong>파이프라인 없음</strong>
          <p className="muted">소스를 등록하고 스케줄을 활성화하면 이 화면에 표시됩니다.</p>
        </div>
      </section>
    )}

    {pipelines.length > 0 && (
      <section className="panel">
        <div className="panelHead">
          <h2>파이프라인 ({pipelines.length})</h2>
          <span className="coordTag">WINDOW {windowHours}H</span>
        </div>
        <div className="tableScroll">
          <table>
            <thead>
              <tr>
                <th>소스</th>
                <th>파이프라인</th>
                <th>상태</th>
                <th>최근 실행</th>
                <th>성공</th>
                <th>실패</th>
                <th>실행 중</th>
                <th>토큰</th>
                <th>평균 소요</th>
                <th>스케줄</th>
                <th>마지막 오류</th>
              </tr>
            </thead>
            <tbody>
              {pipelines.map(p => {
                const total = (p.success_window || 0) + (p.failed_window || 0) + (p.running || 0);
                return <tr key={`${p.source_id}::${p.pipeline_id}`}>
                  <td>
                    <button
                      type="button"
                      className="linkBtn"
                      onClick={() => onOpenSource && onOpenSource(p.source_id)}
                      title={`소스 ${p.source_id} 열기`}
                    >
                      {p.source_id}
                    </button>
                  </td>
                  <td>
                    <span className="pill small">
                      {PIPELINE_LABEL[p.pipeline_id] || p.pipeline_id}
                    </span>
                  </td>
                  <td>
                    {p.last_status ? (
                      <span className={`pill small ${p.last_status}`}>
                        {STATUS_PILL[p.last_status] || p.last_status}
                      </span>
                    ) : <span className="muted">-</span>}
                  </td>
                  <td>
                    {p.last_run_id ? (
                      <button
                        type="button"
                        className="linkBtn mono"
                        onClick={() => onOpenRun && onOpenRun(p.last_run_id)}
                        title={p.last_run_id}
                      >
                        {p.last_run_id.slice(0, 14)}…
                      </button>
                    ) : <span className="muted">-</span>}
                    <div className="muted mono" style={{fontSize: 11}}>
                      {fmtRelative(p.last_run_at)}
                    </div>
                  </td>
                  <td className="num">{p.success_window || 0}</td>
                  <td className={`num ${p.failed_window ? 'warn' : ''}`}>{p.failed_window || 0}</td>
                  <td className="num">{p.running || 0}</td>
                  <td className="num">{nf.format(p.total_tokens_window || 0)}</td>
                  <td className="num">
                    {p.mean_duration_sec ? fmtDur(p.mean_duration_sec) : '-'}
                  </td>
                  <td>
                    {p.enabled_schedule ? (
                      <div title={p.schedule_cron || ''}>
                        <span className="pill small ok">활성</span>
                        <div className="muted mono" style={{fontSize: 10}}>
                          {p.schedule_branch_role} · {p.schedule_label}
                        </div>
                      </div>
                    ) : <span className="muted">-</span>}
                  </td>
                  <td className="auditDetail" title={p.last_error}>
                    {p.last_error
                      ? <>
                          <span className={`pill small ${p.last_error_kind === 'not_found' ? 'bad' : 'warn'}`}>
                            {fmtErrKind(p.last_error_kind) || '오류'}
                          </span>
                          <div className="muted" style={{fontSize: 11, marginTop: 2, maxWidth: 220}}>
                            {String(p.last_error).slice(0, 80)}
                          </div>
                        </>
                      : <span className="muted">-</span>}
                  </td>
                </tr>;
              })}
            </tbody>
          </table>
        </div>
        <div className="panelFoot mono muted">
          {generatedAt ? `생성 시각: ${fmtClock(Date.parse(generatedAt))}` : ''}
        </div>
      </section>
    )}

    {/* 실행 이력 — (source × pipeline) 헬스 아래 시간순 표. 기존 RunsPage 통합. */}
    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead">
        <h2><History size={14} /> 실행 이력</h2>
        <span className="coordTag">{dbRuns.length} RUNS</span>
      </div>
      {dbRunsIsLoading && <LoadingBlock />}
      {dbRunsIsError && <ErrorBanner message={dbRunsError?.message} onRetry={onRetryDbRuns} />}
      {!dbRunsIsLoading && !dbRunsIsError && (
        dbRuns.length
          ? <RunsTable rows={dbRuns} onSelect={onOpenRun} onTrigger={onTrigger} sources={sources} />
          : <div className="emptyPanel">
              <strong>run 이력이 없습니다</strong>
              <p className="muted">저장소에서 소스를 실행하면 이곳에 기록됩니다.</p>
            </div>
      )}
    </section>
  </div>;
}

function Kpi({icon: Icon, label, value, hint, warn, good}) {
  const cls = warn ? 'stat warn' : good ? 'stat good' : 'stat';
  return <section className={cls}>
    <div className="statIcon"><Icon size={16} /></div>
    <div>
      <div className="statLabel">{label}</div>
      <div className="statValue">{value}</div>
      <div className="statHint">{hint || '\u00a0'}</div>
    </div>
  </section>;
}
