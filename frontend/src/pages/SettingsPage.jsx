import React, {useState} from 'react';
import {AlertTriangle, CheckCircle2, KeyRound, Save, Server, Cpu, FileText} from 'lucide-react';
import {PageHeader} from '../components/PageHeader.jsx';
import {DocsHubPanel} from '../components/DocsHubPanel.jsx';
import {InstancesPanel} from '../components/InstancesPanel.jsx';
import {useLlmSettingsQuery} from '../hooks/queries.js';

/**
 * SettingsPage — 시스템급 구성을 한 곳으로.
 * Sections:
 *   1. 인증       — Control Plane API 토큰
 *   2. LLM        — provider/model/key 상태 (.env 기반, 읽기 전용)
 *   3. 문서 허브   — MR 산출물 타깃 저장소 (DocsHubPanel 이관)
 *   4. SCM 인스턴스 — GitLab/GitHub 공용 인스턴스 (InstancesPanel 이관)
 */
export function SettingsPage({
  // docs hub
  targetForm, onTargetFormChange, onSaveTarget,
  // instances
  instances, instanceForm, onInstanceFormChange, onSaveInstance, onToggleInstanceEnabled,
  // shared
  busy, message, pushToast,
}) {
  return <div>
    <PageHeader
      eyebrow="SYSTEM"
      title="설정"
      description="인증, LLM 런타임, 문서 허브, SCM 인스턴스 — 시스템급 구성을 한 곳에서"
    />

    <div className="settingsSections">
      <section className="panel" id="auth">
        <div className="panelHead"><h2><KeyRound size={14} />인증</h2><span className="coordTag">CONTROL API</span></div>
        <AuthSection onSaved={() => pushToast?.('API 토큰을 저장했습니다', 'success')} />
      </section>

      <section className="panel" id="llm">
        <div className="panelHead"><h2><Cpu size={14} />LLM 런타임</h2><span className="coordTag">DATA PLANE</span></div>
        <SectionBoundary label="LLM 섹션">
          <LlmSection />
        </SectionBoundary>
      </section>

      <section className="panel" id="docs-hub">
        <div className="panelHead"><h2><FileText size={14} />문서 허브 (MR 타깃)</h2><span className="coordTag">OUTPUT</span></div>
        <DocsHubPanel target={targetForm} onChange={onTargetFormChange} onSave={onSaveTarget} busy={busy} message={message} embedded />
      </section>

      <section className="panel" id="instances">
        <div className="panelHead"><h2><Server size={14} />SCM 인스턴스</h2><span className="coordTag">CONNECTORS</span></div>
        <InstancesPanel instances={instances} form={instanceForm} onChange={onInstanceFormChange} onSave={onSaveInstance} onToggleEnabled={onToggleInstanceEnabled} busy={busy} message={message} embedded />
      </section>
    </div>
  </div>;
}

// ── 인증 섹션 ──────────────────────────────────────────────────────────

function AuthSection({onSaved}) {
  const [value, setValue] = useState(localStorage.getItem('cp_token') || '');
  const [revealed, setRevealed] = useState(false);
  const hasToken = !!value.trim();
  const save = () => {
    if (value.trim()) localStorage.setItem('cp_token', value.trim());
    else localStorage.removeItem('cp_token');
    onSaved?.();
  };
  return <div className="authSection">
    <div className="settingRow">
      <div className="settingRowCopy">
        <strong>Control Plane API 토큰</strong>
        <p>서버 <code className="mono">CONTROL_API_TOKENS</code> 설정 시 필요. 비우면 개발 무인증 모드.</p>
      </div>
      <span className={`pill small ${hasToken ? 'done' : 'stalled'}`}>{hasToken ? '설정됨' : '미설정'}</span>
    </div>
    <div className="settingControl">
      <input
        type={revealed ? 'text' : 'password'}
        className="settingInput"
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder="API 토큰 (비우면 dev 무인증)"
      />
      <button type="button" className="iconTextBtn" onClick={() => setRevealed(!revealed)}>{revealed ? '숨기기' : '표시'}</button>
      <button type="button" className="primaryBtn" onClick={save}><Save size={15} />저장</button>
    </div>
  </div>;
}

// ── LLM 섹션 (읽기 전용 — .env 기반) ───────────────────────────────────

// 다른 에이전트가 import를 떨어뜨려도 페이지 전체가 죽지 않도록 격리.
class _SectionBoundary extends React.Component {
  constructor(p) { super(p); this.state = {err: null}; }
  static getDerivedStateFromError(err) { return {err}; }
  componentDidCatch() { /* swallow — render fallback */ }
  render() {
    if (this.state.err) return <div className="formMessage errText">{this.props.label} 로드 실패</div>;
    return this.props.children;
  }
}
const SectionBoundary = _SectionBoundary;

function LlmSection() {
  const {data, isLoading, isError, error} = useLlmSettingsQuery();
  if (isLoading) return <div className="settingRow"><div className="settingRowCopy"><strong>로드 중…</strong></div></div>;
  if (isError) return <div className="settingRow"><div className="settingRowCopy"><strong>LLM 설정 조회 실패</strong><p className="errText">{error?.message}</p></div></div>;
  if (!data) return null;

  const fields = [
    {label: 'PROVIDER', value: data.provider || '-'},
    {label: 'MODEL', value: data.model || '-'},
    {label: 'BASE URL', value: data.base_url || '(기본)'},
    {label: 'MAX TOKENS', value: String(data.max_tokens ?? '-')},
    {label: 'TEMPERATURE', value: String(data.temperature ?? '-')},
    {label: 'TIMEOUT', value: `${data.timeout_sec ?? '-'}s`},
    {label: 'RETRY', value: String(data.retry_attempts ?? '-')},
  ];

  return <div className="llmSection">
    <div className="settingRow">
      <div className="settingRowCopy">
        <strong>API 키 상태</strong>
        <p><code className="mono">LLM_API_KEY</code> 환경변수 — 키 값은 서버에서 노출하지 않습니다.</p>
      </div>
      <span className={`pill small ${data.has_key ? 'done' : 'failed'}`}>
        {data.has_key ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
        {data.has_key ? '구성됨' : '미구성'}
      </span>
    </div>
    <dl className="metaList metaListGrid">
      {fields.map(f => <div key={f.label}><dt>{f.label}</dt><dd className="mono">{f.value}</dd></div>)}
    </dl>
    {!data.has_key && <p className="formMessage errText">
      키가 없습니다. <code className="mono">backend/.env</code>의 <code className="mono">LLM_API_KEY</code>를 채우고 서버를 재기동하세요.
    </p>}
    <p className="formMessage">
      이 값들은 서버 시작 시 <code className="mono">.env</code>에서 로드됩니다. 갱신하려면 파일을 수정한 뒤 Control Plane을 재기동하세요.
    </p>
  </div>;
}
