import {LiveFeed} from '../components/LiveFeed.jsx';
import {AgentConversation} from '../components/AgentConversation.jsx';
import {MissionKpis} from '../components/MissionKpis.jsx';
import {StageTable} from '../components/StageTable.jsx';
import {TokenChart} from '../components/TokenChart.jsx';
import {Stat} from '../components/Stat.jsx';
import {Activity, Bot, Braces, Clock3, Layers3, SquareTerminal} from 'lucide-react';
import {fmtDur, fmtNum, nf} from '../lib/format.js';

// 개발자 전용 원시 지표 뷰 — 토큰/도구 수치, 이벤트 버블, 원시 스테이지 테이블
export function TracePage({S, live, state, stages}) {
  const done = stages.filter(s => s.status === 'done').length;
  const failed = stages.filter(s => s.status === 'failed').length;

  return <div>
    <section className="stats">
      <Stat label="입력 토큰" value={fmtNum(S.inTok)} hint={S.inTok ? nf.format(S.inTok) : ''} icon={Braces} />
      <Stat label="출력 토큰" value={fmtNum(S.outTok)} hint={S.outTok ? nf.format(S.outTok) : ''} icon={Bot} />
      <Stat label="LLM 호출" value={nf.format(S.llmCalls)} hint={S.retries ? `재시도 ${S.retries}` : ''} icon={Activity} />
      <Stat label="도구 호출" value={nf.format(S.toolCalls)} hint={S.toolErr ? `실패 ${S.toolErr}` : ''} icon={SquareTerminal} />
      <Stat label="스테이지" value={`${done}/${stages.length}`} hint={failed ? `실패 ${failed}` : '완료/전체'} icon={Layers3} />
      <Stat label="경과" value={fmtDur(S.firstTs ? (live ? Date.now() : S.lastTs) - S.firstTs : 0)} hint="" icon={Clock3} />
    </section>

    <MissionKpis S={S} stages={stages} state={state} />

    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead"><h2>토큰 추이</h2></div>
      <TokenChart series={S.series} />
    </section>

    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead"><h2>스테이지 원시 데이터</h2></div>
      <StageTable S={S} live={live} />
    </section>

    <div className="traceGrid">
      <section className="panel">
        <div className="panelHead"><h2>에이전트 라이브 피드</h2></div>
        <LiveFeed feed={S.feed} />
      </section>
      <section className="panel">
        <div className="panelHead"><h2>대화 로그</h2></div>
        <AgentConversation feed={S.feed} />
      </section>
    </div>
  </div>;
}
