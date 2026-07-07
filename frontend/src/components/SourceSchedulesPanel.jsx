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

function draftFromSchedule(row) {
  const schedule = scheduleFromSource(row);
  return {
    label: row?.label || '정적 문서 자동화',
    pipeline_id: row?.pipeline_id || 'static',
    mode: row?.mode || 'auto',
    branch_role: row?.branch_role || 'dev',
    schedule_time: schedule.time,
    schedule_weekdays: schedule.weekdays,
    enabled: row?.enabled !== false,
  };
}

function schedulePayload(draft) {
  return {
    ...draft,
    schedule_cron: buildCron(draft.schedule_time, draft.schedule_weekdays),
  };
}

function ScheduleForm({draft, onChange, onSave, onDelete, busy, submitLabel}) {
  const toggleWeekday = (day) => {
    const selected = draft.schedule_weekdays.includes(day)
      ? draft.schedule_weekdays.filter(d => d !== day)
      : [...draft.schedule_weekdays, day];
    const ordered = WEEKDAYS.map(d => d.id).filter(d => selected.includes(d));
    if (ordered.length) onChange({...draft, schedule_weekdays: ordered});
  };
  return <div className="scheduleEditor">
    <div className="scheduleEditorHead">
      <span><CalendarClock size={14} />{formatSchedule({time: draft.schedule_time, weekdays: draft.schedule_weekdays})}</span>
      <small className="mono">{buildCron(draft.schedule_time, draft.schedule_weekdays)}</small>
    </div>
    <div className="formGrid">
      <label>스케줄 이름<input value={draft.label} onChange={e => onChange({...draft, label: e.target.value})} /></label>
      <label>파이프라인<select value={draft.pipeline_id} onChange={e => onChange({...draft, pipeline_id: e.target.value})}>
        <option value="static">정적 문서 파이프라인</option>
      </select></label>
      <label>실행 모드<select value={draft.mode} onChange={e => onChange({...draft, mode: e.target.value})}>
        <option value="auto">auto</option>
        <option value="init">init</option>
        <option value="diff">diff</option>
      </select></label>
      <label>브랜치 역할<select value={draft.branch_role} onChange={e => onChange({...draft, branch_role: e.target.value})}>
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
