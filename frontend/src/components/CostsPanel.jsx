import {fmtNum} from '../lib/format.js';

export function CostsPanel({costs, overview}) {
  const bySource = Object.entries(costs?.by_source || {});
  const byModel = Object.values(costs?.by_model || {});
  return <div>
    <div className="missionKpis">
      <div><span>총 입력 토큰</span><strong>{fmtNum(costs?.total_input_tokens || 0)}</strong><small>전체 run 누적</small></div>
      <div><span>총 출력 토큰</span><strong>{fmtNum(costs?.total_output_tokens || 0)}</strong><small>전체 run 누적</small></div>
      <div><span>최근 run</span><strong>{overview?.totals?.runs ?? '-'}</strong><small>완료 {overview?.totals?.done ?? 0} · 실패 {overview?.totals?.failed ?? 0}</small></div>
      <div><span>최근 도구 호출</span><strong>{fmtNum(overview?.totals?.tool_calls || 0)}</strong><small>오류 {overview?.totals?.errors ?? 0}</small></div>
    </div>
    <div className="tableScroll">
      <table>
        <thead><tr><th>소스</th><th>run 수</th><th>실패</th><th>입력 토큰</th><th>출력 토큰</th><th>합계</th></tr></thead>
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
    <div className="panelHead sectionHead">
      <h2>모델별 사용량</h2>
      <span>{byModel.length} models</span>
    </div>
    <div className="tableScroll">
      <table>
        <thead><tr><th>provider</th><th>model</th><th>run 수</th><th>호출</th><th>입력 토큰</th><th>출력 토큰</th><th>합계</th></tr></thead>
        <tbody>
          {byModel.length ? byModel.map(agg => <tr key={`${agg.provider}:${agg.model}`}>
            <td className="mono strong">{agg.provider || 'unknown'}</td>
            <td className="mono strong">{agg.model || 'unknown'}</td>
            <td>{agg.runs || '-'}</td>
            <td>{fmtNum(agg.calls || 0)}</td>
            <td>{fmtNum(agg.input_tokens || 0)}</td>
            <td>{fmtNum(agg.output_tokens || 0)}</td>
            <td>{fmtNum((agg.input_tokens || 0) + (agg.output_tokens || 0))}</td>
          </tr>) : <tr><td colSpan={7} className="emptyCell">모델별 사용량 없음 — 새 usage 이벤트부터 저장됩니다</td></tr>}
        </tbody>
      </table>
    </div>
  </div>;
}
