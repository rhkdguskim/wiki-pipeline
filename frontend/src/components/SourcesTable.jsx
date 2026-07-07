import {Pencil, Play, ShieldCheck} from 'lucide-react';
import {formatSchedule} from '../lib/schedule.js';

export function SourcesTable({sources, onOpenDetail, onVerify, onTrigger, onEdit, onToggleEnabled}) {
  return <div className="tableScroll">
    <table>
      <thead>
        <tr>
          <th>이름</th><th>종류</th><th>repo</th><th>dev</th><th>release</th>
          <th>last sha</th><th>스케줄</th><th>상태</th><th></th>
        </tr>
      </thead>
      <tbody>
        {sources.length ? sources.map(s => <tr key={s.id} className="clickable" onClick={() => onOpenDetail(s.id)}>
          <td className="mono strong">{s.label}</td>
          <td>{s.kind}</td>
          <td>{s.project_id}</td>
          <td>{s.dev_branch || '-'}</td>
          <td>{s.release_branch || '-'}</td>
          <td className="mono">{s.last_processed_sha ? s.last_processed_sha.slice(0, 10) : '-'}</td>
          <td>{s.schedules?.length > 1 ? `${s.schedules.length}개` : formatSchedule(s.schedules?.[0] || s)}</td>
          <td>
            <span className={`stageState ${s.enabled ? 'done' : 'idle'}`}><span />{s.enabled ? '활성' : '비활성'}</span>
            {!s.enabled && s.disabled_reason && <div className="errText">{s.disabled_reason}</div>}
          </td>
          <td onClick={e => e.stopPropagation()}>
            <div className="panelActions">
              <button type="button" className="iconTextBtn" onClick={() => onVerify(s.id)} title="토큰·접근 검증"><ShieldCheck size={14} /></button>
              <button type="button" className="iconTextBtn" disabled={!s.enabled} onClick={() => onTrigger(s.id)} title={s.enabled ? '지금 실행' : s.disabled_reason || '비활성 소스'}><Play size={14} /></button>
              <button type="button" className="iconTextBtn" onClick={() => onEdit(s)} title="수정"><Pencil size={14} /></button>
              <button type="button" className="iconTextBtn" onClick={() => onToggleEnabled(s)} title={s.enabled ? '비활성화 (소프트 삭제)' : '활성화'}>
                {s.enabled ? '비활성화' : '활성화'}
              </button>
            </div>
          </td>
        </tr>) : <tr><td colSpan={9} className="emptyCell">등록된 소스 없음 — 소스를 추가하세요</td></tr>}
      </tbody>
    </table>
  </div>;
}
