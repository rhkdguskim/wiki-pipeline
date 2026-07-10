export const WEEKDAYS = [
  {id: 'mon', label: '월'},
  {id: 'tue', label: '화'},
  {id: 'wed', label: '수'},
  {id: 'thu', label: '목'},
  {id: 'fri', label: '금'},
  {id: 'sat', label: '토'},
  {id: 'sun', label: '일'},
];

const DEFAULT_WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri'];

// 수동 파이프라인은 backend 가 mode=auto / branch_role=release 만 허용 (api.py:1073-1074).
// UI 에서도 잘못된 모드가 저장되지 않도록 강제한다.
export const STATIC_MODES = ['auto', 'init', 'diff'];

// 새 스케줄 초안 기본값.
export const blankSchedule = {
  label: '정적 문서 자동화',
  pipeline_id: 'static',
  mode: 'auto',
  branch_role: 'dev',
  schedule_time: '20:00',
  schedule_weekdays: ['mon', 'tue', 'wed', 'thu', 'fri'],
  enabled: true,
};

export function defaultLabelFor(pipelineId) {
  return pipelineId === 'manual' ? '매뉴얼 자동화' : '정적 문서 자동화';
}

// 서버에서 온 스케줄 행 → 편집용 draft.
export function draftFromSchedule(row) {
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

// 편집 draft → 저장 payload. 매뉴얼이면 mode/branch_role 을 강제 정규화하고 cron 을 합성.
export function schedulePayload(draft) {
  const mode = draft.pipeline_id === 'manual' ? 'auto' : draft.mode;
  const branch_role = draft.pipeline_id === 'manual' ? 'release' : draft.branch_role;
  return {
    ...draft,
    mode,
    branch_role,
    schedule_cron: buildCron(draft.schedule_time, draft.schedule_weekdays),
  };
}

export function scheduleFromSource(source = {}) {
  const schedule = source.schedule || parseCron(source.schedule_cron);
  return {
    time: source.schedule_time || schedule.time || '20:00',
    weekdays: source.schedule_weekdays || schedule.weekdays || DEFAULT_WEEKDAYS,
    label: schedule.label || formatSchedule(schedule),
  };
}

export function buildCron(time, weekdays) {
  const [hour = '20', minute = '00'] = String(time || '20:00').split(':');
  const selected = WEEKDAYS.map(d => d.id).filter(id => (weekdays || DEFAULT_WEEKDAYS).includes(id));
  const dayExpr = compressDays(selected);
  return `${Number(minute)} ${Number(hour)} * * ${dayExpr}`;
}

export function formatSchedule(sourceOrSchedule = {}) {
  const schedule = sourceOrSchedule.schedule ? scheduleFromSource(sourceOrSchedule) : sourceOrSchedule;
  const weekdays = schedule.weekdays?.length ? schedule.weekdays : DEFAULT_WEEKDAYS;
  const labels = WEEKDAYS.filter(d => weekdays.includes(d.id)).map(d => d.label).join('·');
  return `${labels} ${schedule.time || '20:00'} KST`;
}

export function parseCron(cron = '') {
  const parts = String(cron || '').trim().split(/\s+/);
  if (parts.length !== 5) return {time: '20:00', weekdays: DEFAULT_WEEKDAYS, label: '월·화·수·목·금 20:00 KST'};
  const [minute, hour, , , dow] = parts;
  const weekdays = expandDays(dow);
  const time = `${String(Number(hour)).padStart(2, '0')}:${String(Number(minute)).padStart(2, '0')}`;
  return {time, weekdays: weekdays.length ? weekdays : DEFAULT_WEEKDAYS, label: formatSchedule({time, weekdays})};
}

function compressDays(days) {
  if (sameDays(days, DEFAULT_WEEKDAYS)) return 'mon-fri';
  if (sameDays(days, WEEKDAYS.map(d => d.id))) return 'mon-sun';
  return days.join(',');
}

function expandDays(expr) {
  const ids = WEEKDAYS.map(d => d.id);
  const out = new Set();
  String(expr || '').toLowerCase().split(',').forEach(part => {
    const trimmed = part.trim();
    if (!trimmed) return;
    if (trimmed.includes('-')) {
      const [start, end] = trimmed.split('-');
      const a = ids.indexOf(start);
      const b = ids.indexOf(end);
      if (a >= 0 && b >= 0) {
        const range = a <= b ? ids.slice(a, b + 1) : [...ids.slice(a), ...ids.slice(0, b + 1)];
        range.forEach(d => out.add(d));
      }
    } else if (ids.includes(trimmed)) {
      out.add(trimmed);
    }
  });
  return ids.filter(d => out.has(d));
}

function sameDays(a, b) {
  return a.length === b.length && a.every((d, idx) => d === b[idx]);
}
