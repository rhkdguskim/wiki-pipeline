import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {
  Activity,
  AlertTriangle,
  Bot,
  Braces,
  CheckCircle2,
  ChevronDown,
  Clock3,
  FileText,
  GitBranch,
  GitPullRequest,
  Layers3,
  Plus,
  PlayCircle,
  Radio,
  RefreshCw,
  Save,
  Search,
  Server,
  SquareTerminal,
  Workflow,
  XCircle,
} from 'lucide-react';
import './styles.css';

// Control Plane 자체 토큰 인증 (CONTROL_API_TOKENS 설정 시): localStorage.cp_token을 모든 API 호출에 첨부
const api = (url, opts = {}) => {
  const token = localStorage.getItem("cp_token");
  const headers = {...(opts.headers || {}), ...(token ? {"X-Api-Token": token} : {})};
  return fetch(url, {...opts, headers});
};

const POLL_MS = 1500;
const RUNS_MS = 10000;
const STALL_SEC = 90;
const FEED_MAX = 90;

const blankSource = {
  id: '',
  label: '',
  kind: 'gitlab',
  url: 'http://wish.mirero.co.kr',
  project_id: '',
  token: '',
  token_header: 'PRIVATE-TOKEN',
  dev_branch: '',
  release_branch: '',
  themes: 'intro,requirements,architecture-overview,component-diagram',
  enabled: true,
};

const defaultDocTarget = {
  id: 'product-common',
  label: 'product-common',
  kind: 'gitlab',
  url: 'http://wish.mirero.co.kr/mirero/project/pcc/product-common',
  project_id: '',
  project_path: 'mirero/project/pcc/product-common',
  token: '',
  token_header: 'PRIVATE-TOKEN',
  default_branch: 'master',
  enabled: false,
};

const emptyState = () => ({
  firstTs: null,
  lastTs: null,
  runStatus: null,
  pipeline: '',
  inTok: 0,
  outTok: 0,
  llmCalls: 0,
  toolCalls: 0,
  toolErr: 0,
  retries: 0,
  stages: new Map(),
  series: [],
  feed: [],
});

const nf = new Intl.NumberFormat('en-US');
const compact = new Intl.NumberFormat('en-US', {notation: 'compact', maximumFractionDigits: 1});

function fmtNum(n) {
  return n >= 10000 ? compact.format(n) : nf.format(n);
}

function fmtDur(ms) {
  if (ms == null || ms < 0) return '-';
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`;
}

function fmtClock(t) {
  return t ? new Date(t).toTimeString().slice(0, 8) : '-';
}

function runState(S, lastAge) {
  if (S.runStatus === 'done') return ['done', '완료'];
  if (S.runStatus === 'failed') return ['failed', '실패'];
  if (lastAge > STALL_SEC) return ['stalled', '활동 없음'];
  return ['running', '실행 중'];
}

function ingest(S, e) {
  const next = {...S, stages: new Map(S.stages), series: [...S.series], feed: [...S.feed]};
  const t = Date.parse(e.ts);
  if (!next.firstTs || t < next.firstTs) next.firstTs = t;
  if (!next.lastTs || t > next.lastTs) next.lastTs = t;
  if (e.pipeline_id) next.pipeline = e.pipeline_id;
  const d = e.detail || {};

  if (e.layer === 'run') {
    next.runStatus = e.status;
    return next;
  }

  if (e.layer === 'stage' || e.layer === 'engine_call') {
    const prev = next.stages.get(e.stage);
    const st = prev || {layer: e.layer, firstTs: t, lastTs: t, status: e.status, in: 0, out: 0, tools: 0};
    next.stages.set(e.stage, {...st, lastTs: t, status: e.status});
    return next;
  }

  if (e.layer === 'agent_step') {
    const prev = next.stages.get(e.stage);
    const st = prev || {layer: 'agent_step', firstTs: t, lastTs: t, status: null, in: 0, out: 0, tools: 0};
    const patched = {...st, lastTs: t};
    if (d.kind === 'usage') {
      next.inTok += d.input_tokens || 0;
      next.outTok += d.output_tokens || 0;
      next.llmCalls += 1;
      patched.in += d.input_tokens || 0;
      patched.out += d.output_tokens || 0;
      next.series.push({t, in: next.inTok, out: next.outTok});
    } else if (d.kind === 'tool_use') {
      next.toolCalls += 1;
      patched.tools += 1;
    } else if (d.kind === 'tool_result' && !d.ok) {
      next.toolErr += 1;
    } else if (d.kind === 'llm_retry') {
      next.retries += 1;
    }
    next.stages.set(e.stage, patched);
    next.feed.push(e);
    if (next.feed.length > FEED_MAX) next.feed.splice(0, next.feed.length - FEED_MAX);
  }
  return next;
}

function Stat({label, value, hint, icon: Icon}) {
  return (
    <section className="stat">
      <div className="statIcon"><Icon size={16} /></div>
      <div>
        <div className="statLabel">{label}</div>
        <div className="statValue">{value}</div>
        <div className="statHint">{hint || '\u00a0'}</div>
      </div>
    </section>
  );
}

function StatusPill({state}) {
  const Icon = state === 'done' ? CheckCircle2 : state === 'failed' ? XCircle : state === 'stalled' ? AlertTriangle : Radio;
  return <span className={`pill ${state}`}><Icon size={14} />{runStateLabel(state)}</span>;
}

function runStateLabel(state) {
  return {done: '완료', failed: '실패', stalled: '활동 없음', running: '실행 중'}[state] || state;
}

function TokenChart({series}) {
  const ref = useRef(null);
  const [tip, setTip] = useState(null);
  const W = 920, H = 230, M = {l: 52, r: 68, t: 12, b: 28};
  if (series.length < 2) return <div className="emptyPanel">usage 이벤트 2건부터 표시됩니다</div>;
  const pts = series.length > 420 ? series.filter((_, i) => i % Math.ceil(series.length / 420) === 0) : series;
  const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
  const max = Math.max(1, pts[pts.length - 1].in, pts[pts.length - 1].out);
  const x = t => M.l + ((t - t0) / Math.max(1, t1 - t0)) * (W - M.l - M.r);
  const y = v => H - M.b - (v / max) * (H - M.t - M.b);
  const path = key => pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p[key]).toFixed(1)}`).join('');
  const grid = [0, 0.25, 0.5, 0.75, 1].map(r => ({v: max * r, y: y(max * r)}));
  const screen = pts.map(p => ({...p, px: x(p.t)}));
  const onMove = ev => {
    const box = ref.current.getBoundingClientRect();
    const vx = ((ev.clientX - box.left) / box.width) * W;
    let best = screen[0];
    for (const p of screen) if (Math.abs(p.px - vx) < Math.abs(best.px - vx)) best = p;
    setTip({p: best, left: Math.min((best.px / W) * box.width + 12, box.width - 180)});
  };
  return (
    <div className="chartWrap" onMouseMove={onMove} onMouseLeave={() => setTip(null)} ref={ref}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {grid.map(g => <g key={g.y}><line x1={M.l} y1={g.y} x2={W - M.r} y2={g.y} /><text x={M.l - 8} y={g.y + 4}>{fmtNum(Math.round(g.v))}</text></g>)}
        <path className="line in" d={path('in')} />
        <path className="line out" d={path('out')} />
        {tip && <line className="cross" x1={tip.p.px} x2={tip.p.px} y1={M.t} y2={H - M.b} />}
        <text x={M.l} y={H - 6}>{fmtClock(t0)}</text>
        <text x={W - M.r} y={H - 6} textAnchor="end">{fmtClock(t1)}</text>
      </svg>
      {tip && <div className="tooltip" style={{left: tip.left, top: 10}}>
        <strong>{fmtClock(tip.p.t)}</strong>
        <span><i className="sw in" />입력 {nf.format(tip.p.in)}</span>
        <span><i className="sw out" />출력 {nf.format(tip.p.out)}</span>
      </div>}
    </div>
  );
}

function StageTable({S, live}) {
  const rows = [...S.stages.entries()].sort((a, b) => a[1].firstTs - b[1].firstTs);
  if (!rows.length) return <div className="emptyPanel">이벤트 대기 중</div>;
  return (
    <div className="tableScroll">
      <table>
        <thead><tr><th>스테이지</th><th>상태</th><th>소요</th><th>in</th><th>out</th><th>도구</th></tr></thead>
        <tbody>
          {rows.map(([name, s]) => {
            const active = s.status == null && live && Date.now() - s.lastTs < 45000;
            const running = s.status === 'running' || active;
            const state = running ? 'running' : (s.status || 'idle');
            const end = running && live ? Date.now() : s.lastTs;
            return <tr key={name}>
              <td className="mono strong">{name}</td>
              <td><span className={`stageState ${state}`}><span />{runStateLabel(state) || '작업'}</span></td>
              <td>{fmtDur(end - s.firstTs)}</td>
              <td>{s.in ? fmtNum(s.in) : '-'}</td>
              <td>{s.out ? fmtNum(s.out) : '-'}</td>
              <td>{s.tools || '-'}</td>
            </tr>;
          })}
        </tbody>
      </table>
    </div>
  );
}

const kindLabel = {thinking: '생각', tool_use: '도구', tool_result: '결과', usage: '토큰', llm_retry: '재시도'};

function feedText(e) {
  const d = e.detail || {};
  if (d.kind === 'thinking') return d.summary || '';
  if (d.kind === 'tool_use') return `${d.tool} ${JSON.stringify(d.input || {}).slice(0, 90)}`;
  if (d.kind === 'tool_result') return `${d.ok ? 'ok' : 'ERR'} ${(d.preview || '').slice(0, 120)}`;
  if (d.kind === 'usage') return `in=${nf.format(d.input_tokens || 0)} out=${nf.format(d.output_tokens || 0)}`;
  if (d.kind === 'llm_retry') return `attempt=${d.attempt} ${d.error || ''}`;
  return JSON.stringify(d).slice(0, 120);
}

function LiveFeed({feed}) {
  if (!feed.length) return <div className="emptyPanel">이벤트 대기 중</div>;
  return <div className="feed">{feed.slice().reverse().map((e, idx) => {
    const d = e.detail || {};
    const err = (d.kind === 'tool_result' && !d.ok) || d.kind === 'llm_retry';
    return <div className="feedRow" key={`${e.ts}-${idx}`}>
      <time>{fmtClock(Date.parse(e.ts))}</time>
      <span className={`kind ${err ? 'err' : ''}`}>{kindLabel[d.kind] || d.kind || '?'}</span>
      <span className="feedStage">{e.stage}</span>
      <span className="feedText">{feedText(e)}</span>
    </div>;
  })}</div>;
}

function AgentRunway({S, live}) {
  const rows = [...S.stages.entries()].sort((a, b) => a[1].firstTs - b[1].firstTs).slice(-8);
  if (!rows.length) return <div className="runway emptyPanel">이벤트 대기 중</div>;
  return <div className="runway">
    {rows.map(([name, s]) => {
      const active = s.status === 'running' || (s.status == null && live && Date.now() - s.lastTs < 45000);
      const state = active ? 'running' : (s.status || 'idle');
      return <div className={`node ${state}`} key={name}>
        <span className="nodeOrb" />
        <div>
          <strong>{name}</strong>
          <small>{runStateLabel(state) || '작업'} · {fmtDur((active && live ? Date.now() : s.lastTs) - s.firstTs)}</small>
        </div>
      </div>;
    })}
  </div>;
}

function MissionKpis({S, stages, state}) {
  const done = stages.filter(s => s.status === 'done').length;
  const total = stages.length || 0;
  const completion = total ? Math.round((done / total) * 100) : 0;
  const toolReliability = S.toolCalls ? Math.round(((S.toolCalls - S.toolErr) / S.toolCalls) * 100) : 100;
  const burn = S.inTok + S.outTok;
  return <div className="missionKpis">
    <div><span>Completion</span><strong>{completion}%</strong><small>{done}/{total} stages</small></div>
    <div><span>Token burn</span><strong>{fmtNum(burn)}</strong><small>in + out</small></div>
    <div><span>Tool reliability</span><strong>{toolReliability}%</strong><small>{S.toolErr} failures</small></div>
    <div><span>Run health</span><strong>{runStateLabel(state)}</strong><small>{S.retries ? `${S.retries} retries` : 'no retries'}</small></div>
  </div>;
}

function AgentConversation({feed}) {
  const events = feed.slice(-24);
  if (!events.length) return <div className="conversation emptyPanel">이벤트 대기 중</div>;
  return <div className="conversation">
    {events.map((e, idx) => {
      const d = e.detail || {};
      const role = d.kind === 'tool_use' ? 'tool' : d.kind === 'tool_result' ? 'result' : d.kind === 'usage' ? 'metric' : d.kind === 'llm_retry' ? 'error' : 'agent';
      return <article className={`bubble ${role}`} key={`${e.ts}-${idx}`}>
        <header><span>{kindLabel[d.kind] || d.kind || 'agent'}</span><time>{fmtClock(Date.parse(e.ts))}</time></header>
        <p>{feedText(e)}</p>
        <footer>{e.stage}</footer>
      </article>;
    })}
  </div>;
}

function MrPlanPanel({plan, busy, message, onSubmit, onRefresh}) {
  if (!plan) return <div className="mrBox emptyMini">MR 계획 대기</div>;
  const blocked = !plan.can_submit;
  return <div className="mrBox">
    <div className="mrHead">
      <div>
        <span className="contextLabel">product-common MR</span>
        <strong>{plan.file_count} files · {fmtNum(plan.total_bytes)}B</strong>
      </div>
      <button className="iconBtn" onClick={onRefresh} title="MR 계획 새로고침"><RefreshCw size={15} /></button>
    </div>
    <div className="mrMeta">
      <span><GitBranch size={13} />{plan.branch_name}</span>
      <span><FileText size={13} />{plan.branch_role}/{plan.target?.default_branch}</span>
    </div>
    <div className="miniList">
      {plan.files.slice(0, 4).map(f => <span key={f.target_path}><b>{f.target_path}</b><em>{fmtNum(f.size)}B</em></span>)}
    </div>
    {!!plan.warnings?.length && <div className="warningList">{plan.warnings.slice(0, 3).map((w, i) => <p key={i}>{w}</p>)}</div>}
    <button className="primaryBtn fullBtn" disabled={busy || blocked} onClick={onSubmit}>
      <GitPullRequest size={15} />MR 요청
    </button>
    <small className={blocked ? 'blockedText' : 'readyText'}>
      {blocked ? (plan.target?.has_token ? 'target 비활성 또는 파일 없음' : '토큰 필요') : '제출 준비 완료'}
    </small>
    {message && <p className="formMessage">{message}</p>}
  </div>;
}

function RunContextPanel({S, activeRun, state, stages, summary, mrPlan, mrBusy, mrMessage, onSubmitMr, onRefreshMr}) {
  const runningStage = [...S.stages.entries()].reverse().find(([, s]) => s.status === 'running');
  const kpi = summary?.kpi;
  const tools = summary?.tools || [];
  const artifacts = summary?.artifacts || [];
  const errors = summary?.errors || [];
  return <aside className="contextPanel">
    <section>
      <span className="contextLabel">Session</span>
      <strong className="contextTitle">{activeRun?.run_id || 'run 대기'}</strong>
      <StatusPill state={state} />
    </section>
    <section>
      <span className="contextLabel">Current stage</span>
      <strong className="contextTitle mono">{runningStage?.[0] || [...S.stages.keys()].at(-1) || '-'}</strong>
    </section>
    <section className="contextGrid">
      <span>LLM</span><strong>{nf.format(kpi?.llm_calls ?? S.llmCalls)}</strong>
      <span>Tools</span><strong>{nf.format(kpi?.tool_calls ?? S.toolCalls)}</strong>
      <span>Errors</span><strong>{nf.format(kpi?.errors ?? (S.toolErr + (state === 'failed' ? 1 : 0)))}</strong>
      <span>Stages</span><strong>{kpi ? `${kpi.stage_done}/${kpi.stage_total}` : `${stages.filter(s => s.status === 'done').length}/${stages.length}`}</strong>
    </section>
    <section>
      <span className="contextLabel">Top tools</span>
      <div className="miniList">
        {tools.slice(0, 5).length ? tools.slice(0, 5).map(t => <span key={t.name}><b>{t.name}</b><em>{t.calls}</em></span>) : <small>tool data 없음</small>}
      </div>
    </section>
    <section>
      <span className="contextLabel">Artifacts</span>
      <div className="miniList">
        {artifacts.slice(0, 5).length ? artifacts.slice(0, 5).map(a => <span key={a.path}><b>{a.name}</b><em>{fmtNum(a.size)}B</em></span>) : <small>artifact 없음</small>}
      </div>
    </section>
    <section>
      <MrPlanPanel plan={mrPlan} busy={mrBusy} message={mrMessage} onSubmit={onSubmitMr} onRefresh={onRefreshMr} />
    </section>
    {!!errors.length && <section>
      <span className="contextLabel">Recent errors</span>
      <div className="errorList">
        {errors.slice(-3).map((e, i) => <p key={`${e.stage}-${i}`}><b>{e.stage}</b>{e.message || e.kind}</p>)}
      </div>
    </section>}
    <section>
      <span className="contextLabel">Token flow</span>
      <TokenChart series={S.series} />
    </section>
  </aside>;
}

function SourceRail({sources, selected, onSelect}) {
  return <aside className="rail">
    <div className="brand"><Bot size={18} /><span>Agent Ops</span></div>
    <div className="railSection">
      <div className="railLabel">Agent Sources</div>
      {sources.length ? sources.map(s => <button key={s.id} className={selected === s.id ? 'sourceBtn active' : 'sourceBtn'} onClick={() => onSelect(s.id)}>
        <Bot size={15} />
        <span><strong>{s.label}</strong><small>{s.kind} · {s.project_id}</small></span>
      </button>) : <div className="railEmpty">등록 없음</div>}
    </div>
  </aside>;
}

function fieldValue(obj, key) {
  const value = obj?.[key];
  return Array.isArray(value) ? value.join(',') : (value ?? '');
}

function SourceEditor({form, onChange, onSave, busy, message}) {
  const set = (key, value) => onChange({...form, [key]: value});
  return <form className="editor" onSubmit={ev => { ev.preventDefault(); onSave(); }}>
    <div className="editorHead"><h2>Source registration</h2><button className="primaryBtn" disabled={busy}><Save size={15} />저장</button></div>
    <div className="formGrid">
      <label>ID<input value={fieldValue(form, 'id')} onChange={e => set('id', e.target.value)} placeholder="sw-rcs" /></label>
      <label>Label<input value={fieldValue(form, 'label')} onChange={e => set('label', e.target.value)} placeholder="SW RCS" /></label>
      <label>Kind<select value={fieldValue(form, 'kind') || 'gitlab'} onChange={e => set('kind', e.target.value)}><option value="gitlab">gitlab</option></select></label>
      <label>Project ID<input value={fieldValue(form, 'project_id')} onChange={e => set('project_id', e.target.value)} placeholder="947" /></label>
      <label className="span2">GitLab URL<input value={fieldValue(form, 'url')} onChange={e => set('url', e.target.value)} /></label>
      <label>Dev branch<input value={fieldValue(form, 'dev_branch')} onChange={e => set('dev_branch', e.target.value)} placeholder="develop" /></label>
      <label>Release branch<input value={fieldValue(form, 'release_branch')} onChange={e => set('release_branch', e.target.value)} placeholder="master" /></label>
      <label className="span2">Themes<input value={fieldValue(form, 'themes')} onChange={e => set('themes', e.target.value)} /></label>
      <label>Token header<input value={fieldValue(form, 'token_header') || 'PRIVATE-TOKEN'} onChange={e => set('token_header', e.target.value)} /></label>
      <label>Token<input value={fieldValue(form, 'token')} onChange={e => set('token', e.target.value)} placeholder="저장 시에만 사용, 응답에는 표시 안 됨" type="password" /></label>
    </div>
    {message && <p className="formMessage">{message}</p>}
  </form>;
}

function DocsHubPanel({target, onChange, onSave, busy, message}) {
  const form = target || defaultDocTarget;
  const set = (key, value) => onChange({...form, [key]: value});
  return <form className="editor docsTarget" onSubmit={ev => { ev.preventDefault(); onSave(); }}>
    <div className="editorHead">
      <div><h2>Docs Hub Target</h2><p>생성 산출물 MR 대상: product-common</p></div>
      <button className="primaryBtn" disabled={busy}><Save size={15} />저장</button>
    </div>
    <div className="formGrid">
      <label>ID<input value={fieldValue(form, 'id') || 'product-common'} onChange={e => set('id', e.target.value)} /></label>
      <label>Label<input value={fieldValue(form, 'label') || 'product-common'} onChange={e => set('label', e.target.value)} /></label>
      <label className="span2">Project URL<input value={fieldValue(form, 'url')} onChange={e => set('url', e.target.value)} /></label>
      <label>Project ID<input value={fieldValue(form, 'project_id')} onChange={e => set('project_id', e.target.value)} placeholder="숫자 id 알면 입력" /></label>
      <label>Project path<input value={fieldValue(form, 'project_path')} onChange={e => set('project_path', e.target.value)} /></label>
      <label>Default branch<input value={fieldValue(form, 'default_branch') || 'master'} onChange={e => set('default_branch', e.target.value)} /></label>
      <label>Token header<input value={fieldValue(form, 'token_header') || 'PRIVATE-TOKEN'} onChange={e => set('token_header', e.target.value)} /></label>
      <label className="span2">MR token<input value={fieldValue(form, 'token')} onChange={e => set('token', e.target.value)} type="password" placeholder="product-common MR 생성/브랜치 push용" /></label>
    </div>
    {message && <p className="formMessage">{message}</p>}
  </form>;
}

function App() {
  const [sources, setSources] = useState([]);
  const [docTargets, setDocTargets] = useState([]);
  const [sourceForm, setSourceForm] = useState(blankSource);
  const [targetForm, setTargetForm] = useState(defaultDocTarget);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [runs, setRuns] = useState([]);
  const [selectedSource, setSelectedSource] = useState('all');
  const [runId, setRunId] = useState('');
  const [offset, setOffset] = useState(0);
  const [lastAge, setLastAge] = useState(0);
  const [S, setS] = useState(emptyState);
  const [runSummary, setRunSummary] = useState(null);
  const [mrPlan, setMrPlan] = useState(null);
  const [mrBusy, setMrBusy] = useState(false);
  const [mrMessage, setMrMessage] = useState('');
  const [tab, setTab] = useState('overview');
  const [query, setQuery] = useState('');
  const polling = useRef(false);

  const refreshSources = async () => {
    const r = await api('/api/sources');
    setSources(await r.json());
  };
  const refreshDocTargets = async () => {
    const r = await api('/api/docs-hub');
    const data = await r.json();
    setDocTargets(data.targets || []);
    setTargetForm(data.targets?.[0] || defaultDocTarget);
  };
  const refreshRuns = async () => {
    const r = await api('/api/runs');
    const data = await r.json();
    setRuns(data);
    if (!runId && data.length) setRunId(data[0].run_id);
  };

  useEffect(() => { refreshSources().catch(() => {}); refreshDocTargets().catch(() => {}); refreshRuns().catch(() => {}); }, []);
  useEffect(() => {
    const id = setInterval(() => { refreshSources().catch(() => {}); refreshDocTargets().catch(() => {}); refreshRuns().catch(() => {}); }, RUNS_MS);
    return () => clearInterval(id);
  }, [runId]);

  const saveSource = async () => {
    setSaveBusy(true);
    setSaveMessage('');
    try {
      const existing = sources.some(s => s.id === sourceForm.id);
      const r = await api(existing ? `/api/sources/${encodeURIComponent(sourceForm.id)}` : '/api/sources', {
        method: existing ? 'PATCH' : 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(sourceForm),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'source 저장 실패');
      setSaveMessage(`source 저장 완료: ${data.label}`);
      await refreshSources();
    } catch (e) {
      setSaveMessage(e.message);
    } finally {
      setSaveBusy(false);
    }
  };

  const saveDocTarget = async () => {
    setSaveBusy(true);
    setSaveMessage('');
    try {
      const id = targetForm.id || 'product-common';
      const existing = docTargets.some(t => t.id === id);
      const r = await api(existing ? `/api/docs-hub/${encodeURIComponent(id)}` : '/api/docs-hub', {
        method: existing ? 'PATCH' : 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(targetForm),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'docs-hub 저장 실패');
      setSaveMessage(`docs-hub target 저장 완료: ${data.label}`);
      await refreshDocTargets();
    } catch (e) {
      setSaveMessage(e.message);
    } finally {
      setSaveBusy(false);
    }
  };

  useEffect(() => {
    setOffset(0);
    setLastAge(0);
    setS(emptyState());
    setRunSummary(null);
    setMrPlan(null);
    setMrMessage('');
  }, [runId]);

  const refreshMrPlan = async () => {
    if (!runId) return;
    const r = await api(`/api/docs-hub/mr-plan?run=${encodeURIComponent(runId)}&target=product-common`);
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'MR 계획 조회 실패');
    setMrPlan(data);
  };

  const submitMr = async () => {
    if (!runId) return;
    setMrBusy(true);
    setMrMessage('');
    try {
      const r = await api('/api/docs-hub/submit-mr', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({run: runId, target: 'product-common', confirm: 'product-common'}),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'MR 요청 실패');
      setMrPlan(data.plan || mrPlan);
      setMrMessage(data.result?.merge_request?.web_url ? `MR 생성 완료: ${data.result.merge_request.web_url}` : 'MR 생성 완료');
    } catch (e) {
      setMrMessage(e.message);
    } finally {
      setMrBusy(false);
    }
  };

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function fetchSummary() {
      try {
        const r = await api(`/api/run-summary?run=${encodeURIComponent(runId)}`);
        if (!r.ok) return;
        const data = await r.json();
        if (!cancelled) setRunSummary(data);
      } catch {
        // projection is optional; live tail still works
      }
    }
    fetchSummary();
    refreshMrPlan().catch(e => setMrMessage(e.message));
    const id = setInterval(fetchSummary, RUNS_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [runId]);

  useEffect(() => {
    async function poll() {
      if (!runId || polling.current) return;
      polling.current = true;
      try {
        let nextOffset = offset;
        let nextAge = lastAge;
        let changed = false;
        let nextState = S;
        for (let i = 0; i < 50; i++) {
          const r = await api(`/api/events?run=${encodeURIComponent(runId)}&offset=${nextOffset}`);
          const data = await r.json();
          if (data.error) break;
          nextOffset = data.offset;
          nextAge = data.age_sec;
          for (const e of data.events) nextState = ingest(nextState, e);
          changed ||= data.events.length > 0;
          if (data.offset >= data.size) break;
        }
        setOffset(nextOffset);
        setLastAge(nextAge);
        if (changed) setS(nextState);
      } catch {
        // next poll retries
      } finally {
        polling.current = false;
      }
    }
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => clearInterval(id);
  }, [runId, offset, lastAge, S]);

  const filteredRuns = useMemo(() => runs.filter(r => selectedSource === 'all' || r.source_id === selectedSource), [runs, selectedSource]);
  const activeRun = runs.find(r => r.run_id === runId);
  const [state] = runState(S, lastAge);
  const live = state === 'running' || state === 'stalled';
  const stages = [...S.stages.values()].filter(s => s.status != null);
  const done = stages.filter(s => s.status === 'done').length;
  const failed = stages.filter(s => s.status === 'failed').length;
  const visibleSources = sources.filter(s => !query || `${s.label} ${s.project_id} ${s.id}`.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    if (!filteredRuns.length) return;
    if (!filteredRuns.some(r => r.run_id === runId)) setRunId(filteredRuns[0].run_id);
  }, [filteredRuns, runId]);

  return (
    <div className="app">
      <SourceRail sources={sources} selected={selectedSource} onSelect={setSelectedSource} />
      <main className="main">
        <header className="topbar">
          <div>
            <h1>Agent View</h1>
            <p>{activeRun?.source_id || 'legacy'} · {S.pipeline || 'pipeline'} · {runId || 'run 대기'}</p>
          </div>
          <div className="toolbar">
            <label className="selectWrap"><GitBranch size={15} /><select value={selectedSource} onChange={e => setSelectedSource(e.target.value)}>
              <option value="all">전체 source</option>
              {sources.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select><ChevronDown size={14} /></label>
            <label className="selectWrap"><PlayCircle size={15} /><select value={runId} onChange={e => setRunId(e.target.value)}>
              {filteredRuns.map(r => <option key={r.run_id} value={r.run_id}>{r.run_id}{r.age_sec < STALL_SEC ? ' ●' : ''}</option>)}
            </select><ChevronDown size={14} /></label>
            <button className="iconBtn" onClick={() => { refreshSources(); refreshRuns(); }} title="새로고침"><RefreshCw size={16} /></button>
            <StatusPill state={state} />
          </div>
        </header>

        <section className="stats">
          <Stat label="입력 토큰" value={fmtNum(S.inTok)} hint={S.inTok ? nf.format(S.inTok) : ''} icon={Braces} />
          <Stat label="출력 토큰" value={fmtNum(S.outTok)} hint={S.outTok ? nf.format(S.outTok) : ''} icon={Bot} />
          <Stat label="LLM 호출" value={nf.format(S.llmCalls)} hint={S.retries ? `재시도 ${S.retries}` : ''} icon={Activity} />
          <Stat label="도구 호출" value={nf.format(S.toolCalls)} hint={S.toolErr ? `실패 ${S.toolErr}` : ''} icon={SquareTerminal} />
          <Stat label="스테이지" value={`${done}/${stages.length}`} hint={failed ? `실패 ${failed}` : '완료/전체'} icon={Layers3} />
          <Stat label="경과" value={fmtDur(S.firstTs ? (live ? Date.now() : S.lastTs) - S.firstTs : 0)} hint={lastAge ? `${lastAge}s age` : ''} icon={Clock3} />
        </section>

        <nav className="tabs">
          {['overview', 'stages', 'feed', 'sources'].map(id => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
            {({overview: 'Run', stages: 'Plan', feed: 'Trace', sources: 'Sources'})[id]}
          </button>)}
        </nav>

        {tab === 'overview' && <div className="agentGrid">
          <section className="agentStage">
            <div className="agentHead">
              <div>
                <span className="eyebrow">Autonomous run</span>
                <h2>{S.pipeline || 'static'} agent</h2>
              </div>
              <StatusPill state={state} />
            </div>
            <AgentRunway S={S} live={live} />
            <MissionKpis S={S} stages={stages} state={state} />
            <AgentConversation feed={S.feed} />
          </section>
          <RunContextPanel
            S={S}
            activeRun={activeRun}
            state={state}
            stages={stages}
            summary={runSummary}
            mrPlan={mrPlan}
            mrBusy={mrBusy}
            mrMessage={mrMessage}
            onSubmitMr={submitMr}
            onRefreshMr={() => refreshMrPlan().catch(e => setMrMessage(e.message))}
          />
        </div>}

        {tab === 'stages' && <section className="panel"><div className="panelHead"><h2>스테이지 진행</h2></div><StageTable S={S} live={live} /></section>}
        {tab === 'feed' && <section className="panel"><div className="panelHead"><h2>에이전트 라이브 피드</h2></div><LiveFeed feed={S.feed} /></section>}
        {tab === 'sources' && <section className="panel">
          <div className="panelHead">
            <h2>Source Registry</h2>
            <div className="panelActions">
              <button className="iconTextBtn" onClick={() => setSourceForm(blankSource)}><Plus size={15} />신규</button>
              <label className="search"><Search size={15} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="source 검색" /></label>
            </div>
          </div>
          <div className="registryLayout">
            <div className="sourceGrid">
              {visibleSources.map(s => <article className="sourceCard" key={s.id} onClick={() => setSourceForm({...s, themes: (s.themes || []).join(','), token: ''})}>
                <div><strong>{s.label}</strong><span>{s.enabled ? 'enabled' : 'disabled'} · {s.kind} · project {s.project_id}</span></div>
                <p>{s.url}</p>
                <dl>
                  <dt>runs</dt><dd>{s.runs}</dd>
                  <dt>dev</dt><dd>{s.dev_branch || '-'}</dd>
                  <dt>release</dt><dd>{s.release_branch || '-'}</dd>
                  <dt>sha</dt><dd className="mono">{s.last_processed_sha ? s.last_processed_sha.slice(0, 12) : '-'}</dd>
                </dl>
                <div className="tagRow">{(s.themes || []).map(t => <span key={t}>{t}</span>)}</div>
              </article>)}
            </div>
            <div className="registrySide">
              <DocsHubPanel target={targetForm} onChange={setTargetForm} onSave={saveDocTarget} busy={saveBusy} message={saveMessage} />
              <SourceEditor form={sourceForm} onChange={setSourceForm} onSave={saveSource} busy={saveBusy} message={saveMessage} />
            </div>
          </div>
        </section>}
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
