import {AlertTriangle, CheckCircle2, Coins, Radio, Server} from 'lucide-react';
import {fmtNum} from '../lib/format.js';

const DAY_MS = 24 * 60 * 60 * 1000;
const STATUS_LABEL = {pending: '대기', running: '실행 중', done: '완료', failed: '실패'};

function timeAgo(iso) {
  if (!iso) return '-';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return '방금';
  if (mins < 60) return `${mins}분 전`;
  const h = Math.round(mins / 60);
  if (h < 24) return `${h}시간 전`;
  return `${Math.round(h / 24)}일 전`;
}

/**
 * Aggregate per-source stats from dbRuns.
 * Returns Map<source_id, {total, total24h, failed24h, done24h, running, tokens, latest}>
 */
function aggregateBySource(dbRuns, sources) {
  const map = new Map();
  for (const s of sources) {
    map.set(s.id, {total: 0, total24h: 0, failed24h: 0, done24h: 0, running: 0, tokens: 0, latest: null});
  }
  const now = Date.now();
  for (const r of dbRuns) {
    let st = map.get(r.source_id);
    if (!st) {
      st = {total: 0, total24h: 0, failed24h: 0, running: 0, tokens: 0, latest: null};
      map.set(r.source_id, st);
    }
    st.total++;
    st.tokens += (r.input_tokens || 0) + (r.output_tokens || 0);
    if (r.status === 'running') st.running++;
    const created = r.created_at ? new Date(r.created_at).getTime() : 0;
    if (created && now - created < DAY_MS) {
      st.total24h++;
      if (r.status === 'failed') st.failed24h++;
      if (r.status === 'done') st.done24h++;
    }
    if (!st.latest || created > new Date(st.latest.created_at || 0).getTime()) {
      st.latest = r;
    }
  }
  return map;
}

/**
 * MonitorDashboard — landing view for the monitor page.
 * Shows aggregate KPIs across all sources + per-source breakdown cards.
 *
 * Props:
 *   dbRuns, sources, onSelectRun(runId), onOpenRepositories
 */
export function MonitorDashboard({dbRuns = [], sources = [], onSelectRun, onOpenRepositories}) {
  const now = Date.now();
  const runs24h = dbRuns.filter(r => r.created_at && now - new Date(r.created_at).getTime() < DAY_MS);
  const failed24h = runs24h.filter(r => r.status === 'failed').length;
  const running = dbRuns.filter(r => r.status === 'running').length;
  const done24h = runs24h.filter(r => r.status === 'done').length;
  const successRate = runs24h.length ? Math.round((done24h / runs24h.length) * 100) : null;
  const tokens24h = runs24h.reduce((s, r) => s + (r.input_tokens || 0) + (r.output_tokens || 0), 0);

  const stats = aggregateBySource(dbRuns, sources);
  const visibleSources = sources.filter(s => s.enabled || stats.get(s.id)?.total > 0);

  return <div className="monitorDash">
    <div className="stats">
      <Kpi icon={Radio} label="24H RUNS" value={String(runs24h.length)} hint={running ? `${running}개 실행 중` : '대기열 비어 있음'} />
      <Kpi icon={AlertTriangle} label="24H 실패" value={String(failed24h)} hint={failed24h ? '확인 필요' : '최근 실패 없음'} warn={failed24h > 0} />
      <Kpi icon={CheckCircle2} label="성공률" value={successRate == null ? '-' : `${successRate}%`} hint={`${done24h}/${runs24h.length || 0} 완료`} good={successRate != null && successRate >= 80 && runs24h.length > 0} />
      <Kpi icon={Server} label="활성 소스" value={String(visibleSources.length)} hint={`전체 ${sources.length}개`} />
      <Kpi icon={Coins} label="24H 토큰" value={fmtNum(tokens24h)} hint="입력+출력 합계" />
    </div>

    <section className="panel">
      <div className="panelHead">
        <h2>저장소별 현황</h2>
        <span className="coordTag">{visibleSources.length} SOURCES</span>
      </div>

      {visibleSources.length === 0 ? (
        <div className="emptyPanel">
          <div style={{display: 'grid', gap: 8, justifyItems: 'center'}}>
            <strong style={{fontFamily: 'var(--font-display)', fontSize: 15}}>등록된 저장소가 없습니다</strong>
            <p style={{color: 'var(--muted)', fontSize: 13, maxWidth: 360, textAlign: 'center', lineHeight: 1.5}}>
              저장소 페이지에서 GitLab 또는 GitHub 리포지토리를 등록하면 이곳에서 저장소별 run 현황을 한눈에 볼 수 있습니다.
            </p>
            <button type="button" className="primaryBtn" onClick={onOpenRepositories}>저장소로 이동</button>
          </div>
        </div>
      ) : (
        <div className="sourceDashGrid">
          {visibleSources.map(s => {
            const st = stats.get(s.id) || {total: 0, total24h: 0, failed24h: 0, running: 0, tokens: 0, latest: null};
            const latest = st.latest;
            const latestStatus = latest?.status;
            return (
              <button
                key={s.id}
                type="button"
                className={`sourceDashCard ${latestStatus || ''} ${st.running ? 'live' : ''}`}
                onClick={() => latest && onSelectRun(latest.run_id)}
                disabled={!latest}
              >
                <div className="sdcHead">
                  <div className="sdcLabel" title={s.label}>{s.label}</div>
                  {latest && <span className={`pill small ${latestStatus}`}>{STATUS_LABEL[latestStatus] || latestStatus}</span>}
                </div>
                <div className="sdcId mono" title={s.id}>{s.id}</div>
                <div className="sdcStats mono">
                  <span><b>{st.total24h}</b> 24h</span>
                  <span className={st.failed24h ? 'warn' : ''}><b>{st.failed24h}</b> 실패</span>
                  <span><b>{fmtNum(st.tokens)}</b> tok</span>
                </div>
                <div className="sdcFoot">
                  <span className="sdcFootLabel">최근 실행</span>
                  <span className="mono">{latest ? timeAgo(latest.created_at) : '-'}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>

    <section className="panel">
      <div className="panelHead">
        <h2>최근 run</h2>
        <span className="coordTag">{dbRuns.length} ITEMS</span>
      </div>
      {dbRuns.length ? (
        <div className="tableScroll">
          <table>
            <thead><tr><th>run</th><th>소스</th><th>상태</th><th>시각</th></tr></thead>
            <tbody>
              {dbRuns.slice(0, 12).map(r => (
                <tr key={r.run_id} className="clickable" onClick={() => onSelectRun(r.run_id)}>
                  <td className="mono strong ellipsis" title={r.run_id}>{r.run_id}</td>
                  <td className="ellipsis" title={r.source_id || ''}>{r.source_id || '-'}</td>
                  <td><span className={`pill small ${r.status || ''}`}>{STATUS_LABEL[r.status] || r.status || '-'}</span></td>
                  <td className="mono">{timeAgo(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="emptyPanel">아직 실행된 run이 없습니다</div>
      )}
    </section>
  </div>;
}

function Kpi({icon: Icon, label, value, hint, warn, good}) {
  const cls = warn ? 'stat warn' : good ? 'stat good' : 'stat';
  return (
    <section className={cls}>
      <div className="statIcon"><Icon size={16} /></div>
      <div>
        <div className="statLabel">{label}</div>
        <div className="statValue">{value}</div>
        <div className="statHint">{hint || '\u00a0'}</div>
      </div>
    </section>
  );
}
