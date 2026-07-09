import {CalendarClock, Plus, Save, Trash2} from 'lucide-react';
import {useMemo, useState} from 'react';
import {buildCron, formatSchedule, scheduleFromSource, WEEKDAYS} from '../lib/schedule.js';

const blankSchedule = {
  label: '정적 문서 자동화',
  pipeline_id: 'static',
  mode: 'auto',
  branch_role: 'dev',
  schedule_time: '20:00',
  schedule_weekdays: ['mon', 'tue', 'wed', 'thu', 'fri'],
  enabled: true,
};

// 수동 파이프라인은 backend 가 mode=auto 만 허용 (api.py:1073-1074).
// UI 에서도 잘못된 모드가 저장되지 않도록 강제한다.
const STATIC_MODES = ['auto', 'init', 'diff'];

function defaultLabelFor(pipelineId) {
  return pipelineId === 'manual' ? '매뉴얼 자동화' : '정적 문서 자동화';
}

function draftFromSchedule(row) {
  const schedule = scheduleFromSource(row);
  const pipelineId = row?.pipeline_id || 'static';
  return {
    label: row?.label || defaultLabelFor(pipelineId),
    pipeline_id: pipelineId,
    mode: pipelineId === 'manual' ? 'auto' : (row?.mode || 'auto'),
    branch_role: row?.branch_role || (pipelineId === 'manual' ? 'release' : 'dev'),
    schedule_time: schedule.time,
    schedule_weekdays: schedule.weekdays,
    enabled: row?.enabled !== false,
  };
}

function schedulePayload(draft) {
  // 매뉴얼이면 backend 가 mode=auto 만 받으므로 폼 값을 무시하고 강제.
  const mode = draft.pipeline_id === 'manual' ? 'auto' : draft.mode;
  const branch_role = draft.pipeline_id === 'manual' ? 'release' : draft.branch_role;
  return {
    ...draft,
    mode,
    branch_role,
    schedule_cron: buildCron(draft.schedule_time, draft.schedule_weekdays),
  };
}

function ScheduleForm({draft, onChange, onSave, onDelete, busy, submitLabel}) {
  const isManual = draft.pipeline_id === 'manual';
  const toggleWeekday = (day) => {
    const selected = draft.schedule_weekdays.includes(day)
      ? draft.schedule_weekdays.filter(d => d !== day)
      : [...draft.schedule_weekdays, day];
    const ordered = WEEKDAYS.map(d => d.id).filter(d => selected.includes(d));
    if (ordered.length) onChange({...draft, schedule_weekdays: ordered});
  };
  // 파이프라인 변경 시 다른 칸도 같이 정리
  const onChangePipeline = (next) => {
    if (next === draft.pipeline_id) return;
    const patch = {pipeline_id: next, label: defaultLabelFor(next)};
    if (next === 'manual') {
      patch.mode = 'auto';
      patch.branch_role = 'release';
    }
    onChange({...draft, ...patch});
  };
  return <div className="scheduleEditor">
    <div className="scheduleEditorHead">
      <span><CalendarClock size={14} />{formatSchedule({time: draft.schedule_time, weekdays: draft.schedule_weekdays})}</span>
      <small className="mono">{buildCron(draft.schedule_time, draft.schedule_weekdays)}</small>
    </div>
    <div className="formGrid">
      <label>스케줄 이름<input value={draft.label} onChange={e => onChange({...draft, label: e.target.value})} /></label>
      <label>파이프라인<select value={draft.pipeline_id} onChange={e => onChangePipeline(e.target.value)}>
        <option value="static">정적 (docu-automation)</option>
        <option value="manual">매뉴얼 (manual-automation)</option>
      </select></label>
      <label>실행 모드<select value={draft.mode} disabled={isManual}
        onChange={e => onChange({...draft, mode: e.target.value})}>
        {STATIC_MODES.map(m => <option key={m} value={m}>{m}</option>)}
      </select></label>
      <label>브랜치 역할<select value={draft.branch_role} disabled={isManual}
        onChange={e => onChange({...draft, branch_role: e.target.value})}>
        <option value="dev">dev</option>
        <option value="release">release</option>
      </select></label>
      <label>실행 시간<input type="time" value={draft.schedule_time} onChange={e => onChange({...draft, schedule_time: e.target.value})} /></label>
      <label className="checkRow"><input type="checkbox" checked={draft.enabled} onChange={e => onChange({...draft, enabled: e.target.checked})} />활성</label>
      <div className="weekdayToggleGroup span2" role="group" aria-label="실행 요일">
        {WEEKDAYS.map(day => <button
          key={day.id}
          type="button"
          className={draft.schedule_weekdays.includes(day.id) ? 'weekdayToggle active' : 'weekdayToggle'}
          onClick={() => toggleWeekday(day.id)}
        >
          {day.label}
        </button>)}
      </div>
      {isManual && <p className="span2 muted smallHint">
        매뉴얼 파이프라인은 mode=auto / branch_role=release 가 고정입니다.
        실행 시 TriggerDialog 에서 MCP endpoint / tool_allowlist 등 추가 옵션을 입력해 실행됩니다.
      </p>}
    </div>
    <div className="panelActions">
      {onDelete && <button type="button" className="iconTextBtn" onClick={onDelete} disabled={busy}><Trash2 size={14} />삭제</button>}
      <button type="button" className="primaryBtn" onClick={() => onSave(schedulePayload(draft))} disabled={busy}><Save size={14} />{submitLabel}</button>
    </div>
  </div>;
}

export function SourceSchedulesPanel({source, onCreate, onUpdate, onDelete, busy}) {
  const schedules = source?.schedules || [];
  const [drafts, setDrafts] = useState({});
  const [newDraft, setNewDraft] = useState(blankSchedule);
  const editableRows = useMemo(() => schedules.map(row => ({
    row,
    draft: drafts[row.id] || draftFromSchedule(row),
  })), [schedules, drafts]);
  const setDraft = (id, draft) => setDrafts(prev => ({...prev, [id]: draft}));

  // 정적/매뉴얼 스케줄이 각각 몇 개씩 있는지 표시
  const counts = useMemo(() => {
    const c = {static: 0, manual: 0};
    for (const r of schedules) {
      const p = r?.pipeline_id || 'static';
      if (c[p] != null) c[p] += 1;
    }
    return c;
  }, [schedules]);

  return <div className="scheduleStack">
    {editableRows.length ? editableRows.map(({row, draft}) => <ScheduleForm
      key={row.id}
      draft={draft}
      onChange={next => setDraft(row.id, next)}
      onSave={payload => onUpdate(row.id, payload)}
      onDelete={() => onDelete(row.id)}
      busy={busy}
      submitLabel="스케줄 저장"
    />) : <div className="emptyPanel">등록된 자동 실행 스케줄이 없습니다</div>}
    <div className="panelHead sectionHead">
      <h2><Plus size={14} />스케줄 추가</h2>
      <p className="panelHint">정적 {counts.static}개 · 매뉴얼 {counts.manual}개</p>
    </div>
    <ScheduleForm
      draft={newDraft}
      onChange={setNewDraft}
      onSave={payload => onCreate(payload)}
      busy={busy}
      submitLabel="스케줄 추가"
    />
  </div>;
}
