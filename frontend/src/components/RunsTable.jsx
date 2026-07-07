import {Play} from 'lucide-react';
import {fmtNum} from '../lib/format.js';

export function RunsTable({rows, onSelect, onTrigger, sources}) {
  return <div className="tableScroll">
    <table>
      <thead><tr><th>run</th><th>source</th><th>mode</th><th>trigger</th><th>상태</th><th>구간</th><th>문서</th><th>토큰 in/out</th><th>MR</th><th>시각</th></tr></thead>
      <tbody>
        {rows.length ? rows.map(r => <tr key={r.run_id} className="clickable" onClick={() => onSelect(r.run_id)}>
          <td className="mono strong">{r.run_id}</td>
          <td>{r.source_id || '-'}</td>
          <td>{r.mode || '-'}</td>
          <td>{r.trigger || '-'}</td>
          <td><span className={`stageState ${r.status || 'idle'}`}><span />{{pending: '대기', running: '실행 중', done: '완료', failed: '실패'}[r.status] || r.status || '-'}</span></td>
          <td className="mono">{r.from_sha ? `${r.from_sha.slice(0, 8)}→${(r.to_sha || '').slice(0, 8)}` : '-'}</td>
          <td>{r.doc_count ?? '-'}</td>
          <td>{r.input_tokens || r.output_tokens ? `${fmtNum(r.input_tokens)}/${fmtNum(r.output_tokens)}` : '-'}</td>
          <td>{r.mr_url ? <a href={r.mr_url} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>MR ↗</a> : (r.error ? <span className="errText" title={r.error}>오류</span> : '-')}</td>
          <td>{r.created_at ? new Date(r.created_at).toLocaleString('ko-KR', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'}) : '-'}</td>
        </tr>) : <tr><td colSpan={10} className="emptyCell">run 이력 없음 — 소스를 등록하고 실행하세요</td></tr>}
      </tbody>
    </table>
    {!!sources.length && <div className="panelActions triggerRow">
      {sources.map(s => <button key={s.id} className="iconTextBtn" disabled={!s.enabled} onClick={() => onTrigger(s.id)} title={s.enabled ? `${s.label} 배치 실행` : s.disabled_reason || '비활성 소스'}>
        <Play size={14} />{s.label} 실행
      </button>)}
    </div>}
  </div>;
}
