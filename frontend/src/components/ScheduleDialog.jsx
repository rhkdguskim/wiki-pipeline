// ScheduleDialog — 스케줄 추가/편집 모달.
//
// 스케줄러 페이지에서 [스케줄 추가] 또는 기존 스케줄 [편집] 시 열린다.
// ScheduleForm(입력 본체)을 감싸고 저장/삭제/취소 버튼을 footer 에 배치한다.
//
// props:
//   open      : 열림 여부
//   source    : 대상 저장소 {id, label}
//   schedule  : 편집 대상 서버 행(있으면 편집 모드) / null(추가 모드)
//   onSave(payload)   : schedulePayload 형태를 받아 저장
//   onDelete()        : 편집 모드에서만 노출
//   onClose()         : 닫기
//   busy      : 저장 중 비활성화

import {useEffect, useRef, useState} from 'react';
import {CalendarClock, Save, Trash2, X} from 'lucide-react';
import {ScheduleForm} from './ScheduleForm.jsx';
import {blankSchedule, draftFromSchedule, schedulePayload} from '../lib/schedule.js';

export function ScheduleDialog({open, source, schedule, onSave, onDelete, onClose, busy = false}) {
  const isEdit = !!schedule;
  const [draft, setDraft] = useState(blankSchedule);

  // 모달이 열릴 때/대상이 바뀔 때 draft 초기화.
  useEffect(() => {
    if (!open) return;
    setDraft(schedule ? draftFromSchedule(schedule) : blankSchedule);
  }, [open, schedule]);

  // ESC 로 닫기 (a11y)
  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => {
      if (e.key === 'Escape' && !busy) { e.preventDefault(); onClose?.(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, busy, onClose]);

  // 첫 입력 요소로 focus (a11y)
  const dialogRef = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const id = requestAnimationFrame(() => {
      const focusable = dialogRef.current?.querySelector(
        'input:not([disabled]):not([type="hidden"]), select:not([disabled]), button:not([disabled])',
      );
      if (focusable) { try { focusable.focus({preventScroll: true}); } catch { focusable.focus(); } }
    });
    return () => cancelAnimationFrame(id);
  }, [open]);

  if (!open || !source) return null;

  const submit = () => { if (!busy) onSave?.(schedulePayload(draft)); };

  return <div className="wizardOverlay" role="dialog" aria-modal="true" aria-label={isEdit ? '스케줄 편집' : '스케줄 추가'} onClick={onClose}>
    <div className="wizardModal" onClick={e => e.stopPropagation()} ref={dialogRef}>
      <div className="wizardHead">
        <div>
          <h2 style={{margin: 0, fontSize: 17, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6}}>
            <CalendarClock size={17} />{isEdit ? '스케줄 편집' : '스케줄 추가'}
          </h2>
          <div className="muted">{source.label} <span className="mono">({source.id})</span></div>
        </div>
        <button className="iconBtn" onClick={onClose} aria-label="닫기"><X size={16} /></button>
      </div>

      <div className="wizardPane wizardBody">
        <ScheduleForm draft={draft} onChange={setDraft} />
      </div>

      <div className="wizardFoot">
        {isEdit && onDelete
          ? <button type="button" className="iconTextBtn danger" onClick={onDelete} disabled={busy}><Trash2 size={14} />삭제</button>
          : <span />}
        <div className="wizardFootRight">
          <button type="button" className="iconTextBtn" onClick={onClose} disabled={busy}>취소</button>
          <button type="button" className="primaryBtn" onClick={submit} disabled={busy}>
            <Save size={14} />{busy ? '저장 중…' : (isEdit ? '스케줄 저장' : '스케줄 추가')}
          </button>
        </div>
      </div>
    </div>
  </div>;
}
