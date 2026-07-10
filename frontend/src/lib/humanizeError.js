// 에러 추상화 — runner/LLM/SCM 이 던지는 raw 에러 원문(파이썬 예외 문자열,
// OpenAI/Anthropic dict, HTTP 코드)을 사용자가 읽고 행동할 수 있는 언어로 바꾼다.
//
// 원칙(frontend-design writing):
//  - 시스템이 아니라 사용자가 아는 말로: "RateLimitError 429" → "API 사용량 한도 초과"
//  - 무엇이 왜 잘못됐고 어떻게 고치는지: title + fix(조치 힌트)
//  - 원문은 버리지 않는다 — raw 로 함께 반환해 "자세히"/툴팁에서 볼 수 있게 한다.
//
// 반환: {kind, title, fix, raw, tone}
//  - kind: 안정적인 분류 키(스타일링·아이콘 분기용)
//  - title: 한 줄 사람 언어 요약 (버튼/셀에 그대로 노출)
//  - fix:   다음 행동 한 줄 (없으면 '')
//  - raw:   원본 에러 문자열 (툴팁·펼침용, 절대 UI 기본 노출 아님)
//  - tone:  'danger' | 'warn'  (rate limit 처럼 일시적/재시도 가능한 것은 warn)

// backend runner/job.py 의 classify_error 및 settings/test 의 error_kind 와 정합.
const KIND_LABEL = {
  rate_limited: {title: 'API 사용량 한도 초과', fix: '공급자 토큰 플랜을 올리거나 잠시 후 다시 실행하세요', tone: 'warn'},
  auth:         {title: 'LLM 인증 실패', fix: '설정 > LLM 런타임에서 API 키를 확인하세요', tone: 'danger'},
  no_credentials: {title: 'LLM API 키 없음', fix: '설정 > LLM 런타임에서 API 키를 저장하세요', tone: 'danger'},
  model_not_found: {title: '모델을 찾을 수 없음', fix: '설정 > LLM 런타임의 모델 이름을 확인하세요', tone: 'danger'},
  not_found:    {title: '저장소·브랜치를 찾을 수 없음', fix: '소스의 저장소 경로와 브랜치를 확인하세요', tone: 'danger'},
  timeout:      {title: '응답 시간 초과', fix: '잠시 후 다시 실행하세요', tone: 'warn'},
  network:      {title: '네트워크 연결 실패', fix: '엔드포인트 주소와 방화벽을 확인하세요', tone: 'danger'},
  quality_gate: {title: '품질 게이트 미통과', fix: '품질 탭에서 지적 사항을 확인하세요', tone: 'warn'},
  unknown:      {title: '실행이 중단됐습니다', fix: '', tone: 'danger'},
};

// error_kind 가 비었을 때 원문 패턴으로 kind 를 추정한다.
// LLM 호출 실패(OpenAIError/RateLimitError 등)는 runner 의 SCM 분류를 타지 않아
// error_kind 가 비어 오는 경우가 많다 — 여기서 문자열을 보고 사람 말로 되돌린다.
function inferKind(raw) {
  const s = String(raw || '').toLowerCase();
  if (!s) return 'unknown';
  // 인증/키
  if (s.includes('missing credentials') || s.includes('no api key') ||
      s.includes('api_key') && s.includes('provide')) return 'no_credentials';
  if (s.includes('rate limit') || s.includes('ratelimit') || s.includes('429') ||
      s.includes('usage limit') || s.includes('token plan')) return 'rate_limited';
  if (s.includes('401') || s.includes('unauthorized') || s.includes('invalid api key') ||
      s.includes('authentication')) return 'auth';
  if (s.includes('model_not_found') || (s.includes('model') && s.includes('not found')))
    return 'model_not_found';
  if (s.includes('404') || s.includes('not found')) return 'not_found';
  if (s.includes('timeout') || s.includes('timed out')) return 'timeout';
  if (s.includes('connection') || s.includes('econnrefused') || s.includes('network') ||
      s.includes('getaddrinfo') || s.includes('name or service not known')) return 'network';
  if (s.includes('quality') && s.includes('gate')) return 'quality_gate';
  return 'unknown';
}

/**
 * raw 에러(문자열)와 선택적 backend error_kind 를 사람 언어로 변환.
 * @param {string} raw          에러 원문 (run.error, report.error 등)
 * @param {string} [errorKind]  backend 가 분류한 kind (있으면 우선)
 * @returns {{kind, title, fix, raw, tone}}
 */
export function humanizeError(raw, errorKind = '') {
  const rawStr = raw == null ? '' : String(raw);
  // backend kind 정규화 (model_not_found 등 표기 흡수).
  let kind = String(errorKind || '').trim();
  if (!kind || !(kind in KIND_LABEL)) kind = inferKind(rawStr);
  const meta = KIND_LABEL[kind] || KIND_LABEL.unknown;
  return {kind, title: meta.title, fix: meta.fix, tone: meta.tone, raw: rawStr};
}
