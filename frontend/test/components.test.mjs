import {strict as assert} from 'node:assert';
import {
  statusBadge, qualityBadge, publishStateBadge,
} from '../src/lib/ingest.js';
import {runStateLabel} from '../src/lib/format.js';

function test(name, fn) {
  try {
    fn();
    console.log(`  ok  ${name}`);
  } catch (e) {
    console.log(`  FAIL ${name}: ${e.message}`);
    process.exitCode = 1;
  }
}

test('runStateLabel covers all new statuses', () => {
  assert.equal(runStateLabel('done_with_warnings'), '경고 완료');
  assert.equal(runStateLabel('failed_quality_gate'), '품질 실패');
  assert.equal(runStateLabel('partial'), '부분 완료');
  assert.equal(runStateLabel('stale'), '지연');
  assert.equal(runStateLabel('timeout'), '시간 초과');
  assert.equal(runStateLabel('cancelled'), '취소');
  assert.equal(runStateLabel('done'), '완료');
});

test('statusBadge returns warning for done_with_warnings', () => {
  const b = statusBadge('done_with_warnings');
  assert.equal(b.tone, 'warning');
  assert.ok(b.label.length > 0);
});

test('statusBadge returns danger for failed_quality_gate', () => {
  const b = statusBadge('failed_quality_gate');
  assert.equal(b.tone, 'danger');
});

test('statusBadge returns danger for failed', () => {
  const b = statusBadge('failed');
  assert.equal(b.tone, 'danger');
});

test('statusBadge returns success for done', () => {
  const b = statusBadge('done');
  assert.equal(b.tone, 'success');
});

test('statusBadge returns muted for unknown status', () => {
  const b = statusBadge('nonexistent');
  assert.equal(b.tone, 'muted');
});

test('qualityBadge null safety', () => {
  const b = qualityBadge(null);
  assert.equal(b.tone, 'muted');
  assert.ok(b.label.length > 0);
});

test('qualityBadge pass tone', () => {
  const b = qualityBadge({status: 'pass', score: 95});
  assert.equal(b.tone, 'success');
});

test('qualityBadge fail tone with score', () => {
  const b = qualityBadge({status: 'fail', score: 40});
  assert.equal(b.tone, 'danger');
});

test('publishStateBadge blocked is danger', () => {
  const b = publishStateBadge('blocked');
  assert.equal(b.tone, 'danger');
});

test('publishStateBadge review_required is warning', () => {
  const b = publishStateBadge('review_required');
  assert.equal(b.tone, 'warning');
});

test('publishStateBadge publishable is success', () => {
  const b = publishStateBadge('publishable');
  assert.equal(b.tone, 'success');
});

test('publishStateBadge unknown is muted', () => {
  const b = publishStateBadge('unknown');
  assert.equal(b.tone, 'muted');
});

test('publishStateBadge null is muted', () => {
  const b = publishStateBadge(null);
  assert.equal(b.tone, 'muted');
});
