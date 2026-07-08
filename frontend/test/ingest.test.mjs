// frontend ingest state + status badges (2026-07-08).
// vitest 가 없으므로 수동 노드 테스트로 import 후 검증.

import {strict as assert} from 'node:assert';
import {
  emptyState, ingest, stateFromRunSummary, statusBadge, qualityBadge,
  publishStateBadge, mergeRunState, RUN_STATUS_VALUES, QUALITY_STATUS_VALUES,
  PUBLISH_STATE_VALUES,
} from '../src/lib/ingest.js';

function test(name, fn) {
  try {
    fn();
    console.log(`  ok  ${name}`);
  } catch (e) {
    console.log(`  FAIL ${name}: ${e.message}`);
    process.exitCode = 1;
  }
}

test('emptyState has quality fields and seenEventIds', () => {
  const s = emptyState();
  assert.equal(s.qualityStatus, 'not_evaluated');
  assert.equal(s.publishState, 'unknown');
  assert.equal(s.publishable, false);
  assert.ok(s.seenEventIds instanceof Set);
  assert.equal(s.snapshotVersion, 0);
  assert.equal(s.lastSeq, 0);
});

test('RUN_STATUS_VALUES contains done_with_warnings and failed_quality_gate', () => {
  assert.ok(RUN_STATUS_VALUES.includes('done_with_warnings'));
  assert.ok(RUN_STATUS_VALUES.includes('failed_quality_gate'));
  assert.ok(RUN_STATUS_VALUES.includes('stale'));
});

test('ingest dedupes by event_id', () => {
  let s = emptyState();
  s = ingest(s, {ts: '2026-07-08T10:00:00Z', layer: 'stage', stage: 'compare',
                  status: 'running', event_id: 'evt-1', seq: 1});
  const before = s.toolCalls;
  s = ingest(s, {ts: '2026-07-08T10:00:00Z', layer: 'stage', stage: 'compare',
                  status: 'done', event_id: 'evt-1', seq: 2});
  assert.equal(s.toolCalls, before);
});

test('ingest detects seq gap', () => {
  let s = emptyState();
  s = ingest(s, {ts: '2026-07-08T10:00:00Z', layer: 'stage', stage: 'compare',
                  status: 'running', event_id: 'evt-1', seq: 1});
  s = ingest(s, {ts: '2026-07-08T10:00:00Z', layer: 'stage', stage: 'compare',
                  status: 'done', event_id: 'evt-2', seq: 5});
  assert.equal(s.eventGapDetected, true);
  assert.equal(s.lastSeq, 5);
});

test('ingest tracks snapshot_version', () => {
  let s = emptyState();
  s = ingest(s, {ts: '2026-07-08T10:00:00Z', layer: 'stage', stage: 'compare',
                  status: 'running', event_id: 'evt-1', seq: 1,
                  snapshot_version: 7});
  assert.equal(s.snapshotVersion, 7);
});

test('ingest captures quality_gate_completed', () => {
  let s = emptyState();
  s = ingest(s, {ts: '2026-07-08T10:00:00Z', layer: 'agent_step',
                  stage: 'grounding-critic', event_id: 'q-1', seq: 1,
                  detail: {kind: 'quality_gate_completed', status: 'pass',
                            score: 92, publishable: true, publish_state: 'publishable'}});
  assert.equal(s.qualityStatus, 'pass');
  assert.equal(s.qualityScore, 92);
  assert.equal(s.publishable, true);
  assert.equal(s.publishState, 'publishable');
});

test('stateFromRunSummary maps quality/evidence/coverage/mr', () => {
  const s = stateFromRunSummary({
    run_id: 'r1', status: 'done_with_warnings', pipeline_id: 'static',
    publishable: true, publish_state: 'review_required',
    quality: {status: 'warning', score: 75, publishable: true,
              publish_state: 'review_required',
              warning_count: 2, error_count: 0, repair_attempts: 1,
              failed_gate: '', gates: []},
    evidence: {item_count: 12, missing: false, unsupported_claim_count: 1},
    coverage: {status: 'pass', percentage: 88.5, threshold: 70,
               reached: 17, expected: 19, missed_count: 2},
    artifact: {installed_version: '1.8.0', smoke_status: 'pass',
               artifact_name: 'app.msi', release_tag: 'v1.8.0'},
    vnc: {available: true, status: 'connected', session_id: 'vnc-1',
          view_only: true, expires_at: '2026-07-09T00:00:00Z'},
    mr: {readiness: 'review_required', blocked_reason: ''},
    snapshot_version: 4,
    kpi: {input_tokens: 100, output_tokens: 50, llm_calls: 5,
          tool_calls: 3, tool_errors: 0},
    stages: [], timeline: [],
  });
  assert.equal(s.qualityStatus, 'warning');
  assert.equal(s.publishState, 'review_required');
  assert.equal(s.evidenceItemCount, 12);
  assert.equal(s.evidenceMissing, false);
  assert.equal(s.coveragePct, 88.5);
  assert.equal(s.artifactVersion, '1.8.0');
  assert.equal(s.vncAvailable, true);
  assert.equal(s.mrReadiness, 'review_required');
  assert.equal(s.snapshotVersion, 4);
  assert.equal(s.dataAvailability.quality, true);
  assert.equal(s.dataAvailability.evidence, true);
  assert.equal(s.dataAvailability.coverage, true);
});

test('stateFromRunSummary degrades legacy run without quality fields', () => {
  const s = stateFromRunSummary({
    run_id: 'r1', status: 'done', pipeline_id: 'static',
    kpi: {input_tokens: 0, output_tokens: 0, llm_calls: 0,
          tool_calls: 0, tool_errors: 0},
    stages: [], timeline: [],
  });
  assert.equal(s.qualityStatus, 'not_evaluated');
  assert.equal(s.publishState, 'unknown');
  assert.equal(s.evidenceMissing, true);
  assert.equal(s.coverageStatus, 'not_applicable');
  assert.equal(s.vncAvailable, false);
});

test('statusBadge handles new status values', () => {
  assert.equal(statusBadge('done_with_warnings').tone, 'warning');
  assert.equal(statusBadge('failed_quality_gate').tone, 'danger');
  assert.equal(statusBadge('partial').tone, 'warning');
  assert.equal(statusBadge('stale').tone, 'warning');
  assert.equal(statusBadge('timeout').tone, 'danger');
  assert.equal(statusBadge('done').tone, 'success');
});

test('qualityBadge tones', () => {
  assert.equal(qualityBadge({status: 'pass'}).tone, 'success');
  assert.equal(qualityBadge({status: 'warning'}).tone, 'warning');
  assert.equal(qualityBadge({status: 'fail'}).tone, 'danger');
  assert.equal(qualityBadge(null).tone, 'muted');
});

test('publishStateBadge tones', () => {
  assert.equal(publishStateBadge('publishable').tone, 'success');
  assert.equal(publishStateBadge('review_required').tone, 'warning');
  assert.equal(publishStateBadge('blocked').tone, 'danger');
  assert.equal(publishStateBadge('unknown').tone, 'muted');
});

test('mergeRunState preserves seenEventIds and bumps snapshotVersion', () => {
  let s = emptyState();
  s.seenEventIds.add('evt-1');
  s.snapshotVersion = 5;
  const merged = mergeRunState(s, {
    run_id: 'r1', status: 'done', pipeline_id: 'static',
    snapshot_version: 8, kpi: {}, stages: [], timeline: [],
    quality: {status: 'pass', score: 95, publishable: true, publish_state: 'publishable',
              warning_count: 0, error_count: 0, repair_attempts: 0, gates: []},
  });
  assert.equal(merged.snapshotVersion, 8);
  assert.ok(merged.seenEventIds.has('evt-1'));
  assert.equal(merged.qualityStatus, 'pass');
});
