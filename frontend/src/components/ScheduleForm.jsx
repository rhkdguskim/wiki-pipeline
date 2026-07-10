import {CalendarClock} from 'lucide-react';
import {buildCron, defaultLabelFor, formatSchedule, STATIC_MODES, WEEKDAYS} from '../lib/schedule.js';

/**
 * ScheduleForm — 스케줄 하나의 편집 필드 본체 (버튼 없음).
 *
 * 폼 필드만 렌더링하고, 저장/삭제 버튼은 호출자(모달 footer 또는 인라인 패널)가
 * 각자 붙인다 — 모달과 인라인 양쪽에서 동일한 입력 UI 를 재사용하기 위함.
 *
 * draft: draftFromSchedule() / blankSchedule 형태.
 */
export function ScheduleForm({draft, onChange}) {
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
  </div>;
}
