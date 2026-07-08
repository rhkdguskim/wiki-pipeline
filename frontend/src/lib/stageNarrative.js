// 스테이지/이벤트를 비개발자가 이해할 수 있는 한국어 문장으로 번역하는 사전.
// 개요·스테이지(비개발자) 탭이 공유한다 — 트레이스(개발자) 탭은 원본 이름을 그대로 쓴다.

const EXACT = {
  'compare': '저장소 변경 사항을 확인하고 있어요',
  'static-diff': '저장소 변경 사항을 확인하고 있어요',
  'plan': '저장소 구조를 파악하고 있어요',
  'static-init': '저장소 구조를 파악하고 있어요',
  'explore': '저장소 구조를 파악하고 있어요',
  'list-tree': '저장소 파일 목록을 가져오고 있어요',
  'plan-filter': '문서화할 파일을 선별하고 있어요',
  'theme-mapping': '변경 파일을 문서 주제에 연결하고 있어요',
  'map': '코드를 읽고 요약하고 있어요',
  'state-advance': '처리 완료 지점을 기록하고 있어요',
  'artifact': '산출물을 정리하고 있어요',
  'deploy': '산출물을 제출 위치에 배치하고 있어요',
  'connect': '저장소와 도구 연결을 확인하고 있어요',
  'coverage': '문서 반영 범위를 확인하고 있어요',
  'lifecycle': '오래된 문서 후보를 정리하고 있어요',
  'observe': '실행 결과를 점검하고 있어요',
  'smoke': '기본 동작을 검증하고 있어요',
  'smoke-test': '기본 동작을 검증하고 있어요',
  'manual-run': '문서를 작성하고 있어요',
  'manual-smoke': '작성된 문서를 검증하고 있어요',
  'traverse-scenario': '수동 문서 시나리오를 탐색하고 있어요',
  'traverse-explore': '문서 작성에 필요한 근거를 탐색하고 있어요',
};

// 실측 스테이지명 예: critic:repo:intro, critic:dev-guide, reduce:dev-guide,
// repo:intro, theme:architecture-overview, unit:parser, summary:parser, write:theme, map:name.
// 더 구체적인(콜론이 많은) 패턴을 먼저 검사해야 한다.
const PREFIX_RULES = [
  [/^critic:repo:(.+)$/, (_, name) => `'${name}' 문서를 검증하고 있어요`],
  [/^critic:(.+)$/, (_, name) => `'${name}' 문서를 검증하고 있어요`],
  [/^verify/, () => '작성된 문서를 검증하고 있어요'],
  [/^reduce:(.+)$/, (_, name) => `'${name}' 문서를 종합하고 있어요`],
  [/^write:(.+)$/, (_, name) => `'${lastSegment(name)}' 문서를 작성하고 있어요`],
  [/^theme:(.+)$/, (_, name) => `'${name}' 문서를 작성하고 있어요`],
  [/^manual:(.+)$/, (_, name) => `'${name}' 매뉴얼 문서를 작성하고 있어요`],
  [/^scenario:(.+)$/, (_, name) => `'${name}' 시나리오를 실행하고 있어요`],
  [/^repo:(.+)$/, (_, name) => `'${name}' 문서를 작성하고 있어요`],
  [/^unit:(.+)$/, (_, name) => `'${name}' 코드를 요약하고 있어요`],
  [/^summary:(.+)$/, (_, name) => `'${name}' 코드를 요약하고 있어요`],
  [/^map:(.+)$/, () => '코드를 읽고 요약하고 있어요'],
];

function lastSegment(name) {
  const parts = name.split(':');
  return parts[parts.length - 1];
}

// 스테이지 이름 -> 사람이 읽는 문장 ("~하고 있어요" 진행형). 매핑에 없으면 이름 그대로 + "작업 중".
export function narrateStage(stageName) {
  if (!stageName) return '작업을 준비하고 있어요';
  if (EXACT[stageName]) return EXACT[stageName];
  for (const [pattern, fn] of PREFIX_RULES) {
    const match = pattern.exec(stageName);
    if (match) return fn(...match);
  }
  return `${stageName} 작업 중`;
}

// 스테이지 이름 -> 체크리스트에 쓸 짧은 명사형 라벨 (진행형 어미 제거)
export function narrateStageLabel(stageName) {
  const sentence = narrateStage(stageName);
  return sentence.replace(/하고 있어요$/, '').replace(/작업 중$/, '작업').trim();
}

// 문서(테마) 단위로 스테이지를 묶기 위한 키 — write/theme/repo/reduce/critic:repo 계열은
// 같은 문서를 다루면 동일한 groupKey를 갖는다. 그 외는 스테이지 이름 자체가 키.
export function stageGroupKey(stageName) {
  const m = /^(?:write|theme|repo|reduce|critic:repo|critic):(.+)$/.exec(stageName);
  return m ? lastSegment(m[1]) : stageName;
}

// critic:*, reduce:* 등은 문서 작성 스테이지에 종속된 "검증/보조" 단계로 취급한다.
export function isAuxStage(stageName) {
  return /^(critic|reduce|verify)/.test(stageName);
}
