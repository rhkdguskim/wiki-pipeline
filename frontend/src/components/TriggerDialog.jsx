// TriggerDialog — 저장소에서 파이프라인을 실행하기 위한 wizard 모달.
//
// 흐름:
//   step 1: 파이프라인 선택 (정적 docu-automation / 매뉴얼 manual-automation)
//   step 2: 옵션
//     - 정적: mode (auto / init / diff), branch_role (dev / release)
//     - 매뉴얼: MCP endpoint URL (필수), transport, host_label/host_ip/host_port,
//               tool_allowlist (CSV), coverage_threshold (0-100)
//               저장된 프로파일이 있으면 미리 채워서 보여준다.
//   step 3: 선택값 요약 + [실행] 버튼 (실제 /api/runs/trigger 호출)
//
// 매뉴얼 파이프라인은 실행 전에 MCP endpoint 가 저장되어 있어야 한다.
// profile 이 비어 있으면 wizard 안에서 입력 → PUT /api/sources/:id/manual-profile
// → 그 다음 /api/runs/trigger.

import {useEffect, useMemo, useRef, useState} from 'react';
import {Cctv, ChevronLeft, ChevronRight, FileText, Monitor, Play, Save, ShieldCheck, X} from 'lucide-react';
import {useManualProfileQuery} from '../hooks/queries.js';

const STEPS = [
  {id: 'pipeline', label: '파이프라인'},
  {id: 'options',  label: '설정'},
  {id: 'review',   label: '확인 & 실행'},
];

const PIPELINE_LABEL = {static: '정적 (docu-automation)', manual: '매뉴얼 (manual-automation)'};
const PIPELINE_BLURB = {
  static: '저장소의 코드/문서를 읽어 테마별 마크다운 문서를 자동 생성합니다. 브랜치의 변경 구간에 따라 init / diff 모드로 동작합니다.',
  manual: 'MCP로 원격 호스트의 앱에 연결해 시나리오를 실행·관측하고 매뉴얼 문서를 생성합니다. release 브랜치/릴리스 아티팩트에 대해 실행하는 것이 일반적입니다.',
};

export function TriggerDialog({open, source, onClose, onSubmit, busy = false, errorMessage = null}) {
  const [step, setStep] = useState(0);
  const [pipelineId, setPipelineId] = useState('static');
  const [mode, setMode] = useState('auto');
  const [branchRole, setBranchRole] = useState('dev');

  // 매뉴얼 프로파일 로컬 상태. 저장된 게 있으면 자동 채움.
  // 정책:
  //   - RCS Server host_* (label/ip/port) 만 입력 받는다.
  //   - vnc_host/vnc_port 는 host_* 와 자동 동기화 (mirror).
  //   - enabled / vnc_enabled 는 매뉴얼 트리거 시 무조건 true.
  const profileQuery = useManualProfileQuery(open && pipelineId === 'manual' ? source?.id : null);
  const profile = profileQuery.data;
  const [manualForm, setManualForm] = useState({
    enabled: true,
    mcp_endpoint_url: '',
    mcp_transport: 'sse',
    host_label: '',
    host_ip: '',
    host_port: '',
    vnc_enabled: true,
    vnc_host: '',
    vnc_port: '',
    tool_allowlist: '',
    coverage_threshold: 70,
    failure_policy: 'block',
  });
  // 프로파일 fetch 후 폼 채우기 — vnc_* 는 host_* 와 같게 정규화.
  useEffect(() => {
    if (!profile || pipelineId !== 'manual') return;
    setManualForm((f) => ({
      ...f,
      enabled: true,                                  // 매뉴얼 실행 시 강제 활성화
      mcp_endpoint_url: profile.mcp_endpoint_url || '',
      mcp_transport: profile.mcp_transport || 'sse',
      host_label: profile.host_label || '',
      host_ip: profile.host_ip || '',
      host_port: profile.host_port || '',
      vnc_enabled: true,                              // VNC Viewer 무조건 활성화
      vnc_host: profile.host_ip || profile.vnc_host || '',
      vnc_port: profile.host_port || profile.vnc_port || '',
      tool_allowlist: Array.isArray(profile.tool_allowlist) ? profile.tool_allowlist.join(', ') : '',
      coverage_threshold: profile.coverage_threshold ?? 70,
      failure_policy: profile.failure_policy || 'block',
    }));
  }, [profile, pipelineId]);

  // 모달이 닫히거나 다른 source 로 바뀌면 wizard 초기화
  useEffect(() => {
    if (open) {
      setStep(0);
      // 정적 모드 기본값을 source 활성 스케줄에서 가져옴 (없으면 auto/dev)
      const schedules = Array.isArray(source?.schedules) ? source.schedules : [];
      const active = schedules.find((s) => s && s.pipeline_id === 'static' && s.enabled !== false);
      setMode(active?.mode || 'auto');
      setBranchRole(active?.branch_role || 'dev');
    }
  }, [open, source?.id]);

  // hooks 순서: useMemo 도 early-return 앞에 와야 React 의 rules-of-hooks 가 깨지지 않는다.
  const isManual = pipelineId === 'manual';
  const endpointEmpty = isManual && !(manualForm.mcp_endpoint_url || '').trim();
  const canGoNext = useMemo(() => {
    if (step === 0) return !!pipelineId;
    if (step === 1 && isManual) return !endpointEmpty;
    return true;
  }, [step, pipelineId, isManual, endpointEmpty]);

  // ESC 키로 모달 닫기 (a11y)
  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => {
      if (e.key === 'Escape' && !busy) {
        e.preventDefault();
        onClose?.();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, busy, onClose]);

  // 모달 열림/단계 변경 시 모달 안의 첫 interactive element 로 focus (a11y).
  // step 이 바뀔 때마다 새 step 안으로 자동으로 focus 가 따라간다.
  const dialogRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    // 다음 frame 에 focus — step 컴포넌트의 첫 인터랙티브가 mount 된 다음.
    const id = requestAnimationFrame(() => {
      const root = dialogRef.current;
      if (!root) return;
      const focusable = root.querySelector(
        'input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])'
      );
      if (focusable) {
        try { focusable.focus({preventScroll: true}); } catch { focusable.focus(); }
      }
    });
    return () => cancelAnimationFrame(id);
  }, [open, step, pipelineId]);

  if (!open || !source) return null;

  const goNext = () => canGoNext && setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const goPrev = () => setStep((s) => Math.max(s - 1, 0));

  const submit = async () => {
    if (isManual) {
      // 매뉴얼은 endpoint 가 저장되어 있어야 backend 가 받아준다.
      // 정책:
      //   - enabled = true (매뉴얼 트리거 자체가 활성화 신호)
      //   - vnc_enabled = true (VNC Viewer 무조건 활성)
      //   - vnc_host / vnc_port 는 host_ip / host_port 의 mirror (RCS Server 와 동일 호스트)
      const payload = {
        ...profile,
        enabled: true,
        mcp_endpoint_url: manualForm.mcp_endpoint_url.trim(),
        mcp_transport: manualForm.mcp_transport,
        host_label: manualForm.host_label,
        host_ip: manualForm.host_ip,
        host_port: manualForm.host_port,
        vnc_enabled: true,
        vnc_host: manualForm.host_ip,
        vnc_port: Number(manualForm.host_port) || 0,
        tool_allowlist: (manualForm.tool_allowlist || '')
          .split(',').map((s) => s.trim()).filter(Boolean),
        coverage_threshold: Number(manualForm.coverage_threshold) || 0,
        failure_policy: manualForm.failure_policy,
      };
      await onSubmit?.(source.id, {
        pipeline_id: 'manual',
        mode: 'auto',
        branch_role: 'release',
        // wizard 가 직접 manual profile save 도 함께 책임진다.
        manualProfilePayload: payload,
      });
      return;
    }
    await onSubmit?.(source.id, {
      pipeline_id: 'static',
      mode,
      branch_role: branchRole,
    });
  };

  return <div className="wizardOverlay" role="dialog" aria-modal="true" aria-label="파이프라인 실행" onClick={onClose}>
    <div className="wizardModal" onClick={e => e.stopPropagation()} ref={dialogRef}>
      <div className="wizardHead">
        <div>
          <h2 style={{margin: 0, fontSize: 17, fontWeight: 600}}>파이프라인 실행</h2>
          <div className="muted">{source.label} <span className="mono">({source.id})</span></div>
        </div>
        <button className="iconBtn" onClick={onClose} aria-label="닫기"><X size={16} /></button>
      </div>

      <div className="wizardSteps" aria-label="wizard 단계">
        {STEPS.map((s, i) => <span key={s.id} className={
          i === step ? 'wizardStep active' : i < step ? 'wizardStep done' : 'wizardStep'
        }>{i + 1}. {s.label}</span>)}
      </div>

      <div className="wizardPane wizardBody">
        {step === 0 && <StepChoosePipeline pipelineId={pipelineId} onChange={setPipelineId} />}
        {step === 1 && isManual && <StepManualOptions
          form={manualForm}
          onChange={setManualForm}
          profile={profile}
        />}
        {step === 1 && !isManual && <StepStaticOptions
          mode={mode} onMode={setMode}
          branchRole={branchRole} onBranch={setBranchRole}
          activeScheduleNote={(() => {
            const schedules = Array.isArray(source?.schedules) ? source.schedules : [];
            const active = schedules.find((s) => s && s.pipeline_id === 'static' && s.enabled !== false);
            return active ? `활성 스케줄에서 가져옴: ${active.label || ''} · ${active.mode}/${active.branch_role}` : null;
          })()}
        />}
        {step === 2 && <StepReview
          source={source} pipelineId={pipelineId}
          mode={mode} branchRole={branchRole}
          manualForm={manualForm}
          isManual={isManual}
          hasProfile={!!profile}
        />}
      </div>

      {errorMessage && <div className="modalError">{errorMessage}</div>}

      <div className="wizardFoot">
        <button type="button" className="iconTextBtn" onClick={onClose} disabled={busy}>취소</button>
        <div className="wizardFootRight">
          {step > 0 && <button type="button" className="iconTextBtn" onClick={goPrev} disabled={busy}><ChevronLeft size={14} />이전</button>}
          {step < STEPS.length - 1
            ? <button type="button" className="primaryBtn" onClick={goNext} disabled={busy || !canGoNext}>
                다음<ChevronRight size={14} />
              </button>
            : <button type="button" className="primaryBtn" onClick={submit} disabled={busy || (isManual && endpointEmpty)}>
                {busy ? '실행 중…' : <><Play size={14} />{isManual ? '매뉴얼 파이프라인 실행' : '정적 파이프라인 실행'}</>}
              </button>
          }
        </div>
      </div>
    </div>
  </div>;
}

function StepChoosePipeline({pipelineId, onChange}) {
  return <div className="wizardProviderGrid">
    <button
      type="button"
      className={`providerCard ${pipelineId === 'static' ? 'active' : ''}`}
      onClick={() => onChange('static')}
    >
      <FileText size={22} />
      <strong>정적 (docu-automation)</strong>
      <small className="muted">{PIPELINE_BLURB.static}</small>
    </button>
    <button
      type="button"
      className={`providerCard ${pipelineId === 'manual' ? 'active' : ''}`}
      onClick={() => onChange('manual')}
    >
      <Monitor size={22} />
      <strong>매뉴얼 (manual-automation)</strong>
      <small className="muted">{PIPELINE_BLURB.manual}</small>
    </button>
  </div>;
}

function StepStaticOptions({mode, onMode, branchRole, onBranch, activeScheduleNote}) {
  return <div className="triggerForm">
    {activeScheduleNote && <div className="formHint">{activeScheduleNote}</div>}
    <label>실행 모드
      <select value={mode} onChange={(e) => onMode(e.target.value)}>
        <option value="auto">auto — 포인터 없으면 init, 있으면 diff</option>
        <option value="init">init — 전 테마 첫 생성</option>
        <option value="diff">diff — last_processed_sha 이후 변경분</option>
      </select>
    </label>
    <label>브랜치 역할
      <select value={branchRole} onChange={(e) => onBranch(e.target.value)}>
        <option value="dev">dev</option>
        <option value="release">release</option>
      </select>
    </label>
  </div>;
}

function StepManualOptions({form, onChange, profile}) {
  // host_* 변경 시 vnc_host / vnc_port 자동 mirror. enabled / vnc_enabled 는 강제 true 이다.
  const set = (k, v) => {
    const next = {...form, [k]: v};
    if (k === 'host_ip') next.vnc_host = v;
    else if (k === 'host_port') next.vnc_port = Number(v) || 0;
    onChange(next);
  };
  const vncTarget = `${form.host_ip || '—'}:${form.host_port || '—'}`;
  return <div className="triggerForm">
    {profile
      ? <div className="formHint ok">저장된 매뉴얼 프로파일이 있습니다. RCS Server 만 변경해도 VNC Viewer 는 자동 동기화됩니다.</div>
      : <div className="formHint warn">저장된 프로파일이 없습니다. RCS Server 호스트 부터 입력해야 backend 가 받아줍니다.</div>}
    <label className="required">MCP endpoint URL
      <input
        type="text"
        value={form.mcp_endpoint_url}
        onChange={(e) => set('mcp_endpoint_url', e.target.value)}
        placeholder="http://sw-rcs-mcp.internal:8765/sse"
      />
    </label>
    <div className="triggerFormRow">
      <label>Transport
        <select value={form.mcp_transport} onChange={(e) => set('mcp_transport', e.target.value)}>
          <option value="sse">sse</option>
          <option value="stdio">stdio</option>
          <option value="websocket">websocket</option>
        </select>
      </label>
      <label>RCS Server 이름 (식별자)
        <input type="text" value={form.host_label} onChange={(e) => set('host_label', e.target.value)} placeholder="SW-RCS 빌드 #37" />
      </label>
    </div>
    <div className="triggerFormRow">
      <label>RCS Server IP
        <input type="text" value={form.host_ip} onChange={(e) => set('host_ip', e.target.value)} placeholder="10.0.0.12" />
      </label>
      <label>RCS Server port
        <input type="number" value={form.host_port} onChange={(e) => set('host_port', e.target.value)} placeholder="22" />
      </label>
    </div>
    <label>Tool allowlist (콤마 구분)
      <input type="text" value={form.tool_allowlist} onChange={(e) => set('tool_allowlist', e.target.value)} placeholder="screenshot, click, hotkey" />
    </label>
    <div className="triggerFormRow">
      <label>Coverage threshold (%)
        <input type="number" min="0" max="100" value={form.coverage_threshold}
          onChange={(e) => set('coverage_threshold', e.target.value)} />
      </label>
      <label>실패 정책
        <select value={form.failure_policy} onChange={(e) => set('failure_policy', e.target.value)}>
          <option value="block">block</option>
          <option value="review_required">review_required</option>
          <option value="continue_with_warnings">continue_with_warnings</option>
        </select>
      </label>
    </div>
    <div className="formHint">
      <Cctv size={13} /> VNC Viewer — <span className="mono">{vncTarget}</span> 에 view-only 모드로 자동 활성화됩니다 (RCS Server 와 동일 호스트).
    </div>
  </div>;
}

function StepReview({source, pipelineId, mode, branchRole, isManual, manualForm, hasProfile}) {
  const vncTarget = `${manualForm.host_ip || '—'}:${manualForm.host_port || '—'}`;
  return <div className="triggerReview">
    <dl className="metaList">
      <dt>저장소</dt><dd>{source.label} <span className="mono">({source.id})</span></dd>
      <dt>파이프라인</dt><dd className="strong">{PIPELINE_LABEL[pipelineId]}</dd>
      {isManual ? <>
        <dt>MCP endpoint</dt><dd className="mono">{manualForm.mcp_endpoint_url || '— (미입력)'}</dd>
        <dt>Transport</dt><dd>{manualForm.mcp_transport}</dd>
        <dt>RCS Server</dt>
        <dd>
          {manualForm.host_label || '—'} <span className="mono">({vncTarget})</span>
        </dd>
        <dt>VNC Viewer</dt>
        <dd><span className="mono">{vncTarget}</span> · view-only · 자동 활성화</dd>
        <dt>Coverage threshold</dt><dd>{manualForm.coverage_threshold}%</dd>
        <dt>Tool allowlist</dt><dd className="mono ellipsis" title={manualForm.tool_allowlist}>{manualForm.tool_allowlist || '—'}</dd>
        <dt>실패 정책</dt><dd>{manualForm.failure_policy}</dd>
      </> : <>
        <dt>모드</dt><dd>{mode}</dd>
        <dt>브랜치</dt><dd>{branchRole}</dd>
      </>}
    </dl>
    {isManual && !hasProfile && <div className="formHint warn">
      저장된 프로파일이 없습니다. 실행 시 wizard 의 값으로 즉시 저장(<Save size={12} />) 후 실행합니다.
    </div>}
    <div className="formHint">
      <ShieldCheck size={12} />실행 후 진행 상황은 [파이프라인 → 실행 이력] 또는 새 run 상단에서 실시간으로 확인됩니다.
    </div>
  </div>;
}
