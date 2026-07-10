import React, {useState} from 'react';
import {AlertTriangle, CheckCircle2, KeyRound, Save, Server, Cpu, FileText, RotateCcw, Eye, EyeOff, Link2, Gauge, Plug2, Loader2, Radio} from 'lucide-react';
import {PageHeader} from '../components/PageHeader.jsx';
import {DocsHubPanel} from '../components/DocsHubPanel.jsx';
import {InstancesPanel} from '../components/InstancesPanel.jsx';
import {useUiStore} from '../store/ui.js';
import {
  useLlmSettingsQuery,
  useUpdateLlmSettingsMutation,
  useResetLlmSettingsMutation,
  useTestLlmConnectionMutation,
} from '../hooks/queries.js';

/**
 * SettingsPage — 시스템급 구성을 한 곳으로.
 * Sections:
 *   1. 인증       — Control Plane API 토큰
 *   2. LLM        — provider/model/key/base_url 등 (DB 영구 저장 + .env 폴백)
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
  const sections = [
    {id: 'auth', label: '인증', icon: KeyRound},
    {id: 'runtime', label: '런타임', icon: Radio},
    {id: 'llm', label: 'LLM 런타임', icon: Cpu},
    {id: 'docs-hub', label: '문서 허브', icon: FileText},
    {id: 'instances', label: 'SCM 인스턴스', icon: Server},
  ];

  return <div>
    <PageHeader
      eyebrow="SYSTEM"
      title="설정"
      description="런타임, 인증, 산출물 대상, SCM 연결을 한 화면에서 관리합니다"
    />

    <div className="settingsLayout">
      <aside className="settingsIndex" aria-label="설정 섹션">
        {sections.map(({id, label, icon: Icon}) => (
          <a key={id} href={`#${id}`} className="settingsIndexLink">
            <Icon size={14} />
            <span>{label}</span>
          </a>
        ))}
      </aside>

      <div className="settingsSections">
        <section className="panel settingsPanel" id="auth">
          <div className="panelHead"><h2><KeyRound size={14} />인증</h2></div>
          <AuthSection onSaved={() => pushToast?.('API 토큰을 저장했습니다', 'success')} />
        </section>

        <section className="panel settingsPanel" id="runtime">
          <div className="panelHead"><h2><Radio size={14} />런타임</h2></div>
          <RuntimeSection />
        </section>

        <section className="panel settingsPanel" id="llm">
          <div className="panelHead"><h2><Cpu size={14} />LLM 런타임</h2></div>
          <SectionBoundary label="LLM 섹션">
            <LlmSection pushToast={pushToast} />
          </SectionBoundary>
        </section>

        <section className="panel settingsPanel" id="docs-hub">
          <div className="panelHead"><h2><FileText size={14} />문서 허브</h2></div>
          <DocsHubPanel target={targetForm} onChange={onTargetFormChange} onSave={onSaveTarget} busy={busy} message={message} embedded />
        </section>

        <section className="panel settingsPanel" id="instances">
          <div className="panelHead"><h2><Server size={14} />SCM 인스턴스</h2></div>
          <InstancesPanel instances={instances} form={instanceForm} onChange={onInstanceFormChange} onSave={onSaveInstance} onToggleEnabled={onToggleInstanceEnabled} busy={busy} message={message} embedded />
        </section>
      </div>
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
  return <form className="authSection" onSubmit={(e) => { e.preventDefault(); save(); }}>
    {/* 보이지 않는 username 필드 — 비밀번호 매니저 접근성 경고 회피용.
        토큰 자체는 사용자명 개념이 없으므로 화면에 노출되지 않게 off-screen 처리. */}
    <input
      type="text"
      name="username"
      autoComplete="username"
      tabIndex={-1}
      aria-hidden="true"
      style={{position: 'absolute', left: '-9999px', width: 1, height: 1, opacity: 0}}
      readOnly
    />
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
        autoComplete="current-password"
        autoCorrect="off"
        spellCheck={false}
        aria-label="Control Plane API 토큰"
      />
      <button type="button" className="iconTextBtn" onClick={() => setRevealed(!revealed)} aria-label={revealed ? '토큰 가리기' : '토큰 표시'}>{revealed ? '숨기기' : '표시'}</button>
      <button type="submit" className="primaryBtn" onClick={save}><Save size={15} />저장</button>
    </div>
  </form>;
}

function RuntimeSection() {
  const wsVerbose = useUiStore(s => s.wsVerbose);
  const setWsVerbose = useUiStore(s => s.setWsVerbose);

  return <div className="runtimeSection">
    <div className="settingRow">
      <div className="settingRowCopy">
        <strong>에이전트 실행 추적</strong>
        <p>실시간 모니터에서 판단 요약, 도구 호출, 결과, 재시도를 수신합니다.</p>
      </div>
      <label className={`settingsToggle ${wsVerbose ? 'on' : ''}`} title="상세 디버깅이 필요할 때만 켜세요.">
        <input
          type="checkbox"
          checked={wsVerbose}
          onChange={e => setWsVerbose(e.target.checked)}
        />
        <span>{wsVerbose ? 'ON' : 'OFF'}</span>
      </label>
    </div>
  </div>;
}

// ── LLM 섹션 (편집 가능 · DB 영구 저장) ───────────────────────────────

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

// 그룹 정의 — 의미 단위로 묶어 시각적 위계 + 여백 확보.
const LLM_GROUPS = [
  {
    key: 'connection', icon: Link2, title: '연결 및 모델',
    fields: ['provider', 'model', 'base_url', 'api_key'],
  },
  {
    key: 'sampling', icon: Gauge, title: '런타임 한도',
    fields: ['max_tokens', 'temperature', 'timeout_sec', 'retry_attempts', 'max_concurrency'],
  },
];

const FIELD_LABEL = {
  provider: 'Provider',
  base_url: 'Base URL',
  api_key: 'API Key',
  model: 'Model',
  max_tokens: 'Max Tokens',
  temperature: 'Temperature',
  timeout_sec: 'Timeout (sec)',
  retry_attempts: 'Retry',
  max_concurrency: '동시 호출 한도',
};

const FIELD_PLACEHOLDER = {
  provider: '',
  base_url: '비우면 공급자 기본 endpoint',
  api_key: '저장된 키 (••••••••) — 바꾸려면 새 키 입력, 비우면 .env 로 복귀',
  model: '예: minimax-m3, gpt-4o, claude-3-5-sonnet',
  max_tokens: '',
  temperature: '',
  timeout_sec: '',
  retry_attempts: '',
  max_concurrency: '0=무제한. Z.AI(GLM)는 3',
};

function LlmSection({pushToast}) {
  const {data, isLoading, isError, error} = useLlmSettingsQuery();
  const updateMut = useUpdateLlmSettingsMutation();
  const resetMut = useResetLlmSettingsMutation();
  const testMut = useTestLlmConnectionMutation();

  const [form, setForm] = useState(null);
  const [revealedKey, setRevealedKey] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [testResult, setTestResult] = useState(null);  // 마지막 테스트 결과

  React.useEffect(() => {
    if (data && !dirty) {
      setForm({
        provider: data.provider || '',
        base_url: data.base_url || '',
        api_key: data.has_key ? '••••••••' : '',
        model: data.model || '',
        max_tokens: data.max_tokens ?? 65536,
        temperature: data.temperature ?? 0.2,
        timeout_sec: data.timeout_sec ?? 180,
        retry_attempts: data.retry_attempts ?? 4,
        max_concurrency: data.max_concurrency ?? 0,
      });
    }
  }, [data, dirty]);

  if (isLoading) return <div className="settingRow"><div className="settingRowCopy"><strong>로드 중…</strong></div></div>;
  if (isError) return <div className="settingRow"><div className="settingRowCopy"><strong>LLM 설정 조회 실패</strong><p className="errText">{error?.message}</p></div></div>;
  if (!data) return null;

  const setField = (k, v) => {
    setForm(f => ({...(f || {}), [k]: v}));
    setDirty(true);
    // 폼이 바뀌면 이전 테스트 결과는 무효 — 가짜 안심 방지.
    if (testResult) setTestResult(null);
  };

  const onSave = async () => {
    try {
      const payload = {...(form || {})};
      if (payload.api_key === '' || payload.api_key === '••••••••') {
        delete payload.api_key;
      }
      await updateMut.mutateAsync(payload);
      setDirty(false);
      pushToast?.('LLM 설정을 저장했습니다. 다음 run부터 런타임에 적용됩니다.', 'success');
    } catch (e) {
      pushToast?.(e.message || 'LLM 설정 저장 실패', 'error');
    }
  };

  const onReset = async () => {
    if (!confirm('LLM settings DB 행을 모두 삭제하고 .env 기본값으로 되돌릴까요?')) return;
    try {
      await resetMut.mutateAsync();
      setDirty(false);
      setTestResult(null);
      pushToast?.('LLM 설정을 .env 기본값으로 되돌렸습니다.', 'success');
    } catch (e) {
      pushToast?.(e.message || '초기화 실패', 'error');
    }
  };

  // 테스트 — 현재 폼 값(저장 안 한 값 포함)을 백엔드로 보내고 결과 표시.
  const onTest = async () => {
    setTestResult(null);
    try {
      const payload = {...(form || {})};
      if (payload.api_key === '' || payload.api_key === '••••••••') {
        delete payload.api_key;
      }
      const r = await testMut.mutateAsync(payload);
      setTestResult(r);
    } catch (e) {
      setTestResult({ok: false, error: e.message || '테스트 실패'});
    }
  };

  const updateBusy = updateMut.isPending || resetMut.isPending;
  const sourceLabel = {db: 'DB 저장값', env: '.env 기본값', partial: '혼합'}[data.source] || data.source;
  const sourcePillCls = data.source === 'db' ? 'done' : data.source === 'env' ? 'stalled' : 'warn';

  return <form className="llmSection" onSubmit={(e) => { e.preventDefault(); if (!dirty || updateBusy) return; onSave(); }}>
    <input
      type="text"
      name="username"
      autoComplete="username"
      tabIndex={-1}
      aria-hidden="true"
      style={{position: 'absolute', left: '-9999px', width: 1, height: 1, opacity: 0}}
      readOnly
    />
    <div className="llmStatusBar">
      <div>
        <span className="settingMetaLabel">현재 소스</span>
        <strong>{sourceLabel}</strong>
      </div>
      <span className={`pill small ${sourcePillCls}`}>
        {data.source === 'db' ? <CheckCircle2 size={12} /> : data.source === 'env' ? <AlertTriangle size={12} /> : null}
        {sourceLabel}
      </span>
      <div>
        <span className="settingMetaLabel">API Key</span>
        <strong>{data.has_key ? '구성됨' : '미구성'}</strong>
      </div>
      <div className="llmApplyNote ok">
        <CheckCircle2 size={13} />
        <span>다음 run부터 자동 적용</span>
      </div>
    </div>

    <div className="llmGroups">
      {LLM_GROUPS.map(g => {
        const GIcon = g.icon;
        return <fieldset className="llmGroup" key={g.key}>
          <div className="llmGroupHead">
            <legend className="llmGroupTitle"><GIcon size={13} />{g.title}</legend>
          </div>
          <div className="llmGroupFields">
            {g.fields.map(fk => {
              const isPassword = fk === 'api_key';
              const isNumber = ['max_tokens', 'temperature', 'timeout_sec', 'retry_attempts', 'max_concurrency'].includes(fk);
              return <label className="llmField" key={fk}>
                <span>{FIELD_LABEL[fk]}</span>
                {fk === 'provider' ? (
                  <select value={form?.[fk] || ''} onChange={e => setField(fk, e.target.value)}>
                    <option value="openai-compatible">openai-compatible</option>
                    <option value="openai">openai</option>
                    <option value="anthropic">anthropic</option>
                  </select>
                ) : (
                  <div className="llmFieldControl">
                    <input
                      type={isPassword ? (revealedKey ? 'text' : 'password') : (isNumber ? 'number' : 'text')}
                      step={fk === 'temperature' ? '0.05' : (['max_concurrency', 'retry_attempts', 'max_tokens'].includes(fk) ? '1' : undefined)}
                      min={isNumber ? (fk === 'max_tokens' ? '256' : '0') : undefined}
                      max={isNumber ? (fk === 'max_tokens' ? '200000' : fk === 'temperature' ? '2' : fk === 'timeout_sec' ? '600' : fk === 'max_concurrency' ? '64' : '10') : undefined}
                      value={form?.[fk] ?? ''}
                      onChange={e => {
                        const v = e.target.value;
                        if (isNumber) setField(fk, v === '' ? '' : Number(v));
                        else setField(fk, v);
                      }}
                      autoComplete={isPassword ? 'off' : undefined}
                      spellCheck={isPassword ? false : undefined}
                      aria-label={FIELD_LABEL[fk]}
                      placeholder={isPassword
                        ? (data.has_key
                            ? '저장된 키 (••••••••) — 바꾸려면 새 키 입력, 비우면 .env 로 복귀'
                            : '비어 있음 — 입력하면 DB 저장')
                        : FIELD_PLACEHOLDER[fk]}
                    />
                    {isPassword && <button type="button" className="iconTextBtn" onClick={() => setRevealedKey(!revealedKey)} title={revealedKey ? '숨기기' : '표시'}>
                      {revealedKey ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>}
                  </div>
                )}
              </label>;
            })}
          </div>
        </fieldset>;
      })}
    </div>

    <div className="llmActions">
      <button type="submit" className="primaryBtn" onClick={onSave} disabled={updateBusy || !dirty}>
        <Save size={15} />{updateBusy ? '저장 중…' : '저장'}
      </button>
      <button type="button" className="iconTextBtn" onClick={onTest} disabled={testMut.isPending} title="현재 폼 값(저장 안 한 것 포함)으로 짧은 LLM 호출 — 연결·키·모델 확인">
        {testMut.isPending ? <Loader2 size={14} className="spin" /> : <Plug2 size={14} />}
        {testMut.isPending ? '테스트 중…' : '연결 테스트'}
      </button>
      <button type="button" className="iconTextBtn" onClick={onReset} disabled={updateBusy} title="DB 에 저장된 LLM settings 모두 삭제 (.env 기본값으로 복귀)">
        <RotateCcw size={14} />.env 로 되돌리기
      </button>
      {dirty ? <span className="dirtyHint">변경 사항이 저장되지 않았습니다.</span>
             : <span className="cleanHint">저장됨</span>}
    </div>

    {/* 연결 테스트 결과 */}
    {testResult && <div className={`llmTestResult ${testResult.ok ? 'ok' : 'bad'}`}>
      {testResult.ok ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
      <div className="llmTestResultBody">
        {testResult.ok ? (
          <>
            <strong>연결 성공</strong>
            <span className="muted"> · {testResult.model} · {testResult.latency_ms}ms</span>
            {testResult.response_preview && (
              <pre className="llmTestPreview">{testResult.response_preview}</pre>
            )}
          </>
        ) : (
          <>
            <strong>연결 실패</strong>
            {testResult.error_kind && <span className="muted"> · {testResult.error_kind}</span>}
            {testResult.error && <pre className="llmTestPreview errText">{testResult.error}</pre>}
          </>
        )}
      </div>
    </div>}
  </form>;
}
