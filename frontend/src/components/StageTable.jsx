import {deriveStageState, fmtDur, fmtNum, runStateLabel} from '../lib/format.js';

export function StageTable({S, live}) {
  const rows = [...S.stages.entries()].sort((a, b) => a[1].firstTs - b[1].firstTs);
  if (!rows.length) return <div className="emptyPanel">이벤트 대기 중</div>;
  return (
    <div className="tableScroll">
      <table>
        <thead><tr><th>스테이지</th><th>상태</th><th>소요</th><th>입력</th><th>출력</th><th>도구</th></tr></thead>
        <tbody>
          {rows.map(([name, s]) => {
            // deriveStageState로 통일 — 빈 문자열 status를 done으로 처리
            const {state} = deriveStageState(s, live);
            const end = state === 'running' && live ? Date.now() : s.lastTs;
            return <tr key={name}>
              <td className="mono strong">{name}</td>
              <td><span className={`stageState ${state}`}><span />{runStateLabel(state) || '작업'}</span></td>
              <td>{fmtDur(end - s.firstTs)}</td>
              <td>{s.in ? fmtNum(s.in) : '-'}</td>
              <td>{s.out ? fmtNum(s.out) : '-'}</td>
              <td>{s.tools || '-'}</td>
            </tr>;
          })}
        </tbody>
      </table>
    </div>
  );
}
