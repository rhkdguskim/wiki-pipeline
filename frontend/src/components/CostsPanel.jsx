import {fmtNum} from '../lib/format.js';

export function CostsPanel({costs, overview}) {
  const bySource = Object.entries(costs?.by_source || {});
  return <div>
    <div className="missionKpis">
      <div><span>총 입력 토큰</span><strong>{fmtNum(costs?.total_input_tokens || 0)}</strong><small>전체 run 누적</small></div>
      <div><span>총 출력 토큰</span><strong>{fmtNum(costs?.total_output_tokens || 0)}</strong><small>전체 run 누적</small></div>
      <div><span>최근 run</span><strong>{overview?.totals?.runs ?? '-'}</strong><small>done {overview?.totals?.done ?? 0} · failed {overview?.totals?.failed ?? 0}</small></div>
      <div><span>최근 도구 호출</span><strong>{fmtNum(overview?.totals?.tool_calls || 0)}</strong><small>errors {overview?.totals?.errors ?? 0}</small></div>
    </div>
    <div className="tableScroll">
      <table>
        <thead><tr><th>source</th><th>runs</th><th>실패</th><th>입력 토큰</th><th>출력 토큰</th><th>합계</th></tr></thead>
        <tbody>
          {bySource.length ? bySource.map(([sid, agg]) => <tr key={sid}>
            <td className="mono strong">{sid}</td>
            <td>{agg.runs}</td>
            <td>{agg.failed || '-'}</td>
            <td>{fmtNum(agg.input_tokens)}</td>
            <td>{fmtNum(agg.output_tokens)}</td>
            <td>{fmtNum(agg.input_tokens + agg.output_tokens)}</td>
          </tr>) : <tr><td colSpan={6} className="emptyCell">비용 데이터 없음 — run이 끝나면 usage 토큰이 집계됩니다</td></tr>}
        </tbody>
      </table>
    </div>
  </div>;
}
