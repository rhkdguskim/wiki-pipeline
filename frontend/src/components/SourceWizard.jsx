import {useMemo, useState} from 'react';
import {CalendarClock, CheckCircle2, ChevronLeft, ChevronRight, GitBranch, Play, Plus, Server, ShieldCheck, X, XCircle} from 'lucide-react';
import {useInstancesQuery, usePreflightSourceMutation, useSaveSourceMutation} from '../hooks/queries.js';
import {buildCron, formatSchedule, WEEKDAYS} from '../lib/schedule.js';

const THEME_OPTIONS = ['intro', 'requirements', 'architecture-overview', 'component-diagram', 'dev-guide', 'api-protocol'];
const STEPS = ['프로바이더', '인스턴스', '레포', '검증', '브랜치', '옵션', '저장'];

const emptyWizard = {
  kind: 'gitlab',
  instanceMode: 'existing', // existing | new
  instanceId: '',
  newInstanceUrl: '',
  newInstanceToken: '',
  newInstanceTokenHeader: 'PRIVATE-TOKEN',
  projectId: '',
  sourceToken: '',
  label: '',
  devBranch: '',
  releaseBranch: '',
  themes: ['intro', 'requirements', 'architecture-overview', 'component-diagram'],
  scheduleTime: '20:00',
  scheduleWeekdays: ['mon', 'tue', 'wed', 'thu', 'fri'],
  ownerEmail: '',
};

export function SourceWizard({onClose, onCreated, onTriggerSuggested}) {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(emptyWizard);
  const [preflightResult, setPreflightResult] = useState(null);
  const [saveMessage, setSaveMessage] = useState('');

  const {data: instances = []} = useInstancesQuery();
  const preflightMutation = usePreflightSourceMutation();
  const saveMutation = useSaveSourceMutation();

  const set = (key, value) => setForm(f => ({...f, [key]: value}));
  const isGithub = form.kind === 'github';
  const matchingInstances = useMemo(() => instances.filter(i => i.kind === form.kind), [instances, form.kind]);

  const canGoNext = () => {
    if (step === 1) return form.instanceMode === 'existing' ? !!form.instanceId : true;
    if (step === 2) return !!form.projectId.trim();
    if (step === 3) return !!preflightResult?.verified;
    if (step === 4) return !!form.devBranch;
    return true;
  };

  const runPreflight = async () => {
    setPreflightResult(null);
    const payload = form.instanceMode === 'existing'
      ? {instance_id: form.instanceId, project_id: form.projectId, token: form.sourceToken}
      : {
        kind: form.kind,
        url: form.newInstanceUrl,
        token: form.sourceToken || form.newInstanceToken,
        token_header: form.newInstanceTokenHeader,
        project_id: form.projectId,
      };
    try {
      const result = await preflightMutation.mutateAsync(payload);
      setPreflightResult(result);
      if (result.verified) {
        set('label', form.label || result.name || form.projectId);
        set('releaseBranch', result.default_branch || '');
      }
    } catch (e) {
      setPreflightResult({verified: false, error: e.message});
    }
  };

  const next = async () => {
    if (step === 2) {
      setStep(3);
      await runPreflight();
      return;
    }
    setStep(s => Math.min(s + 1, STEPS.length - 1));
  };
  const back = () => setStep(s => Math.max(s - 1, 0));

  const toggleTheme = t => set('themes', form.themes.includes(t) ? form.themes.filter(x => x !== t) : [...form.themes, t]);
  const toggleWeekday = day => {
    const selected = form.scheduleWeekdays.includes(day)
      ? form.scheduleWeekdays.filter(d => d !== day)
      : [...form.scheduleWeekdays, day];
    const ordered = WEEKDAYS.map(d => d.id).filter(d => selected.includes(d));
    if (ordered.length) set('scheduleWeekdays', ordered);
  };

  const save = async () => {
    setSaveMessage('');
    const sourceForm = {
      id: (form.label || form.projectId).toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/(^-|-$)/g, ''),
      label: form.label || form.projectId,
      kind: form.kind,
      url: form.instanceMode === 'existing'
        ? (matchingInstances.find(i => i.id === form.instanceId)?.base_url || '')
        : form.newInstanceUrl,
      instance_id: form.instanceMode === 'existing' ? form.instanceId : undefined,
      project_id: form.projectId,
      token: form.sourceToken,
      token_header: form.newInstanceTokenHeader,
      dev_branch: form.devBranch,
      release_branch: form.releaseBranch,
      themes: form.themes.join(','),
      owner_email: form.ownerEmail,
      schedule_time: form.scheduleTime,
      schedule_weekdays: form.scheduleWeekdays,
      schedule_cron: buildCron(form.scheduleTime, form.scheduleWeekdays),
      enabled: true,
      verify: false,
    };
    try {
      const created = await saveMutation.mutateAsync({form: sourceForm, existing: false});
      setSaveMessage(`소스 등록 완료: ${created.label}`);
      onCreated?.(created);
    } catch (e) {
      setSaveMessage(e.message);
    }
  };

  return (
    <div className="wizardOverlay" onClick={onClose}>
      <div className="wizardModal" onClick={e => e.stopPropagation()}>
        <div className="wizardHead">
          <h2>소스 추가</h2>
          <button className="iconBtn" onClick={onClose} title="닫기"><X size={16} /></button>
        </div>
        <div className="wizardSteps">
          {STEPS.map((label, i) => <span key={label} className={i === step ? 'wizardStep active' : i < step ? 'wizardStep done' : 'wizardStep'}>{i + 1}. {label}</span>)}
        </div>

        <div className="wizardBody">
          {step === 0 && <div className="wizardProviderGrid">
            <button type="button" className={form.kind === 'gitlab' ? 'providerCard active' : 'providerCard'} onClick={() => { set('kind', 'gitlab'); set('instanceId', ''); set('instanceMode', 'existing'); }}>
              <Server size={28} /><strong>GitLab</strong><small>사내 GitLab · gitlab.com</small>
            </button>
            <button type="button" className={form.kind === 'github' ? 'providerCard active' : 'providerCard'} onClick={() => { set('kind', 'github'); set('instanceId', ''); set('instanceMode', 'existing'); }}>
              <GitBranch size={28} /><strong>GitHub</strong><small>github.com</small>
            </button>
          </div>}

          {step === 1 && <div className="wizardPane">
            <div className="checkRow">
              <label><input type="radio" checked={form.instanceMode === 'existing'} onChange={() => set('instanceMode', 'existing')} />기존 인스턴스 사용</label>
              <label><input type="radio" checked={form.instanceMode === 'new'} onChange={() => set('instanceMode', 'new')} />새 인스턴스</label>
            </div>
            {form.instanceMode === 'existing' ? (
              <div className="miniList">
                {matchingInstances.length ? matchingInstances.map(i => (
                  <label key={i.id} className={`checkRow${form.instanceId === i.id ? ' active' : ''}`}>
                    <input type="radio" checked={form.instanceId === i.id} onChange={() => set('instanceId', i.id)} />
                    <b>{i.label || i.id}</b><em>{i.base_url || '(기본 URL)'} · {i.has_token ? '토큰 있음' : '토큰 없음'}</em>
                  </label>
                )) : <small>등록된 {form.kind} 인스턴스가 없습니다 — 새 인스턴스를 선택하세요.</small>}
              </div>
            ) : (
              <div className="formGrid">
                <label className="span2">{isGithub ? 'URL (비우면 github.com)' : 'GitLab URL'}<input value={form.newInstanceUrl} onChange={e => set('newInstanceUrl', e.target.value)} placeholder={isGithub ? 'https://github.com (기본)' : 'http://wish.mirero.co.kr'} /></label>
                <label>토큰 헤더<input value={form.newInstanceTokenHeader} onChange={e => set('newInstanceTokenHeader', e.target.value)} /></label>
                <label>토큰<input value={form.newInstanceToken} onChange={e => set('newInstanceToken', e.target.value)} type="password" placeholder="인스턴스 공용 토큰" /></label>
              </div>
            )}
          </div>}

          {step === 2 && <div className="wizardPane">
            <div className="formGrid">
              <label className="span2">{isGithub ? '레포 (owner/repo)' : '프로젝트 ID 또는 전체 경로'}<input value={form.projectId} onChange={e => set('projectId', e.target.value)} placeholder={isGithub ? 'owner/repo' : '947 또는 mirero/project/x'} /></label>
              <label className="span2">소스 전용 토큰 (선택 — 비우면 인스턴스 토큰 사용)<input value={form.sourceToken} onChange={e => set('sourceToken', e.target.value)} type="password" placeholder="비워두면 인스턴스 토큰 사용" /></label>
            </div>
          </div>}

          {step === 3 && <div className="wizardPane">
            {preflightMutation.isPending && <div className="emptyPanel">검증 중…</div>}
            {!preflightMutation.isPending && preflightResult && (
              <div className={preflightResult.verified ? 'verifyBox ok' : 'verifyBox bad'}>
                {preflightResult.verified ? <>
                  <p><CheckCircle2 size={13} /> 검증 성공 — <b>{preflightResult.name}</b> ({preflightResult.namespace_path})</p>
                  <p>default branch <b>{preflightResult.default_branch}</b> · HEAD <span className="mono">{(preflightResult.head_sha || '').slice(0, 12)}</span></p>
                  <p>브랜치 {preflightResult.branches?.length || 0}개</p>
                </> : <p><XCircle size={13} /> 검증 실패: {preflightResult.error}</p>}
              </div>
            )}
            {!preflightMutation.isPending && !preflightResult?.verified && (
              <button type="button" className="iconTextBtn" onClick={runPreflight}><ShieldCheck size={15} />다시 검증</button>
            )}
          </div>}

          {step === 4 && <div className="wizardPane">
            <div className="formGrid">
              <label>dev 브랜치<select value={form.devBranch} onChange={e => set('devBranch', e.target.value)}>
                <option value="">선택</option>
                {(preflightResult?.branches || []).map(b => <option key={b} value={b}>{b}</option>)}
              </select></label>
              <label>release 브랜치<select value={form.releaseBranch} onChange={e => set('releaseBranch', e.target.value)}>
                <option value="">(default branch 사용)</option>
                {(preflightResult?.branches || []).map(b => <option key={b} value={b}>{b}</option>)}
              </select></label>
            </div>
          </div>}

          {step === 5 && <div className="wizardPane">
            <div className="formGrid">
              <label className="span2">Label<input value={form.label} onChange={e => set('label', e.target.value)} /></label>
              <label className="span2">테마
                <div className="tagRow">
                  {THEME_OPTIONS.map(t => (
                    <label key={t} className="checkRow"><input type="checkbox" checked={form.themes.includes(t)} onChange={() => toggleTheme(t)} />{t}</label>
                  ))}
                </div>
              </label>
              <div className="scheduleEditor span2">
                <div className="scheduleEditorHead">
                  <span><CalendarClock size={14} />자동 실행 스케줄</span>
                  <small>{formatSchedule({time: form.scheduleTime, weekdays: form.scheduleWeekdays})}</small>
                </div>
                <label>실행 시간<input type="time" value={form.scheduleTime} onChange={e => set('scheduleTime', e.target.value)} /></label>
                <div className="weekdayToggleGroup" role="group" aria-label="실행 요일">
                  {WEEKDAYS.map(day => <button
                    key={day.id}
                    type="button"
                    className={form.scheduleWeekdays.includes(day.id) ? 'weekdayToggle active' : 'weekdayToggle'}
                    onClick={() => toggleWeekday(day.id)}
                  >
                    {day.label}
                  </button>)}
                </div>
              </div>
              <label>담당자 이메일<input value={form.ownerEmail} onChange={e => set('ownerEmail', e.target.value)} placeholder="실패 알림 수신자" /></label>
            </div>
          </div>}

          {step === 6 && <div className="wizardPane">
            <p className="formMessage">
              <b>{form.label || form.projectId}</b> ({form.kind}) · dev={form.devBranch || '-'} · release={form.releaseBranch || '(default)'}
            </p>
            {saveMessage && <p className="formMessage">{saveMessage}</p>}
          </div>}
        </div>

        <div className="wizardFoot">
          <button type="button" className="iconTextBtn" onClick={back} disabled={step === 0}><ChevronLeft size={15} />이전</button>
          {step < STEPS.length - 1
            ? <button type="button" className="primaryBtn" disabled={!canGoNext() || preflightMutation.isPending} onClick={next}>다음<ChevronRight size={15} /></button>
            : <button type="button" className="primaryBtn" disabled={saveMutation.isPending || !!saveMutation.data} onClick={save}><Plus size={15} />소스 저장</button>}
          {saveMutation.data && (
            <button type="button" className="iconTextBtn" onClick={() => { onTriggerSuggested?.(saveMutation.data.id); onClose(); }}><Play size={15} />지금 실행</button>
          )}
        </div>
      </div>
    </div>
  );
}
