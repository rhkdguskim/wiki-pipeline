import {CheckCircle2, Circle, XCircle} from 'lucide-react';
import {deriveStageState, fmtDur} from '../lib/format.js';
import {isAuxStage, narrateStageLabel, stageGroupKey} from '../lib/stageNarrative.js';

// critic:*/reduce:* 같은 보조 스테이지를 같은 문서를 다루는 주 스테이지 밑에 묶는다.
// 순서는 최초 등장 순(firstTs) 유지, 보조 스테이지는 해당 그룹 뒤에 따라붙는다.
function groupStages(rows) {
  const groups = new Map(); // groupKey -> {main, aux: []}
  const order = [];
  for (const [name, s] of rows) {
    const key = stageGroupKey(name);
    if (!groups.has(key)) {
      groups.set(key, {main: null, aux: []});
      order.push(key);
    }
    const g = groups.get(key);
    if (isAuxStage(name)) g.aux.push([name, s]);
    else if (!g.main) g.main = [name, s];
    else g.aux.push([name, s]); // 같은 키에 주 스테이지가 이미 있으면 보조로
  }
  return order.map(key => {
    const g = groups.get(key);
    // 주 스테이지가 없으면(예: critic만 단독 등장) 첫 보조를 주로 승격
    if (!g.main && g.aux.length) g.main = g.aux.shift();
    return {key, main: g.main, aux: g.aux};
  }).filter(g => g.main);
}

function StatusIcon({state}) {
  if (state === 'done') return <CheckCircle2 size={18} />;
  if (state === 'failed') return <XCircle size={18} />;
  if (state === 'running') return <span className="spinner" />;
  return <Circle size={18} />;
}

export function StageChecklist({S, live}) {
  const rows = [...S.stages.entries()].sort((a, b) => a[1].firstTs - b[1].firstTs);
  if (!rows.length) return <div className="emptyPanel">이벤트 대기 중</div>;
  const groups = groupStages(rows);

  return <ul className="checklist">
    {groups.map(({key, main, aux}) => {
      const [mainName, mainStage] = main;
      const {state, end} = deriveStageState(mainStage, live);
      // 보조 스테이지 중 하나라도 실행 중이면 주 항목도 "검증 중"으로 보이도록 상태를 승격
      const auxStates = aux.map(([, s]) => deriveStageState(s, live));
      const auxRunning = auxStates.some(a => a.state === 'running');
      const effectiveState = state === 'done' && auxRunning ? 'running' : state;
      const latestEnd = Math.max(end, ...auxStates.map(a => a.end));
      const label = narrateStageLabel(mainName);
      const auxLabel = aux.length ? aux.map(([n]) => narrateStageLabel(n)).join(' · ') : '';

      return <li className={`checklistItem ${effectiveState}`} key={key}>
        <span className="checklistIcon"><StatusIcon state={effectiveState} /></span>
        <div className="checklistBody">
          <strong className="ellipsis" title={label}>{label}</strong>
          {auxLabel && <span className="checklistHint ellipsis" title={auxLabel}>{auxLabel}</span>}
        </div>
        <span className="checklistDur">{mainStage.firstTs ? fmtDur(latestEnd - mainStage.firstTs) : '-'}</span>
      </li>;
    })}
  </ul>;
}
