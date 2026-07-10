import {strict as assert} from 'node:assert';
import {humanizeError} from '../src/lib/humanizeError.js';

function test(name, fn) {
  try {
    fn();
    console.log(`  ok  ${name}`);
  } catch (e) {
    console.log(`  FAIL ${name}: ${e.message}`);
    process.exitCode = 1;
  }
}

test('backend error_kind wins when present', () => {
  const h = humanizeError('some raw text', 'rate_limited');
  assert.equal(h.kind, 'rate_limited');
  assert.equal(h.title, 'API 사용량 한도 초과');
  assert.equal(h.tone, 'warn');
  assert.ok(h.fix.length > 0);
});

test('infers no_credentials from OpenAIError missing credentials', () => {
  const raw = 'OpenAIError: Missing credentials. Please pass an `api_key`, ... or set the `OPENAI_API_KEY`';
  const h = humanizeError(raw);
  assert.equal(h.kind, 'no_credentials');
  assert.equal(h.title, 'LLM API 키 없음');
  assert.equal(h.tone, 'danger');
});

test('infers rate_limited from 429 / token plan', () => {
  const raw = "RateLimitError: Error code: 429 - {'type': 'error', 'error': {'type': 'rate_limit_error', 'message': 'Token Plan usage limit reached'}}";
  const h = humanizeError(raw);
  assert.equal(h.kind, 'rate_limited');
  assert.equal(h.tone, 'warn');
});

test('infers auth from 401 unauthorized', () => {
  assert.equal(humanizeError('401 Unauthorized: invalid api key').kind, 'auth');
});

test('infers not_found from 404', () => {
  assert.equal(humanizeError('compare 404: project not found').kind, 'not_found');
});

test('infers network from connection refused', () => {
  assert.equal(humanizeError('ECONNREFUSED connect to host').kind, 'network');
});

test('empty error → unknown, raw preserved', () => {
  const h = humanizeError('');
  assert.equal(h.kind, 'unknown');
  assert.equal(h.raw, '');
  assert.equal(h.title, '실행이 중단됐습니다');
});

test('raw is always preserved verbatim', () => {
  const raw = 'RateLimitError: Error code: 429 - {full dict here}';
  assert.equal(humanizeError(raw).raw, raw);
});

test('unknown backend kind falls back to inference', () => {
  // error_kind 가 우리 맵에 없으면 원문 추론으로 폴백
  const h = humanizeError('Missing credentials', 'weird_unmapped_kind');
  assert.equal(h.kind, 'no_credentials');
});
