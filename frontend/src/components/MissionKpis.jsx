import {fmtNum, runStateLabel} from '../lib/format.js';

export function MissionKpis({S, stages, state}) {
  const done = stages.filter(s => s.status === 'done').length;
  const total = stages.length || 0;
  const completion = total ? Math.round((done / total) * 100) : 0;
  const toolReliability = S.toolCalls ? Math.round(((S.toolCalls - S.toolErr) / S.toolCalls) * 100) : 100;
  const burn = S.inTok + S.outTok;
  return <div className="missionKpis">
    <div><span>완료율</span><strong>{completion}%</strong><small>{done}/{total} 스테이지</small></div>
    <div><span>토큰 사용량</span><strong>{fmtNum(burn)}</strong><small>입력+출력 합계</small></div>
    <div><span>도구 성공률</span><strong>{toolReliability}%</strong><small>실패 {S.toolErr}건</small></div>
    <div><span>실행 상태</span><strong>{runStateLabel(state)}</strong><small>{S.retries ? `재시도 ${S.retries}회` : '재시도 없음'}</small></div>
  </div>;
}
