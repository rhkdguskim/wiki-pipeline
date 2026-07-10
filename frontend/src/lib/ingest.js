// ingest state + event reducer — Karpathy LLM Wiki 의 "ingest" 단계.
// 2026-07-08: quality/coverage/artifact/VNC/seq dedupe/gap-detection 추가.

export const FEED_MAX = 90;
export const AGENT_TRACE_MAX = 600;

export const RUN_STATUS_VALUES = [
  'pending', 'running',
  'done', 'done_with_warnings',
  'failed', 'failed_quality_gate', 'partial', 'stale',
  'cancelled', 'timeout',
];

export const QUALITY_STATUS_VALUES = ['pass', 'warning', 'fail', 'not_evaluated'];

export const PUBLISH_STATE_VALUES = [
  'publishable', 'review_required', 'blocked', 'unknown',
];

export const emptyState = () => ({
  firstTs: null,
  lastTs: null,
  runStatus: null,
  pipeline: '',
  inTok: 0,
  outTok: 0,
  llmCalls: 0,
  modelUsage: new Map(),
  toolCalls: 0,
  toolErr: 0,
  retries: 0,
  stages: new Map(),
  series: [],
  feed: [],
  agentFeed: [],
  qualityStatus: 'not_evaluated',
  qualityScore: null,
  publishable: false,
  publishState: 'unknown',
  failedGate: null,
  warningCount: 0,
  errorCount: 0,
  repairAttempts: 0,
  evidenceItemCount: 0,
  evidenceMissing: true,
  unsupportedClaimCount: 0,
  coveragePct: null,
  coverageThreshold: null,
  coverageStatus: 'not_applicable',
  coverageReached: 0,
  coverageExpected: 0,
  coverageMisses: [],
  artifactVersion: null,
  artifactStatus: 'unknown',
  artifactReleaseTag: null,
  mrReadiness: 'unknown',
  mrBlockedReason: '',
  vncAvailable: false,
  vncStatus: 'unavailable',
  vncSessionId: '',
  vncViewOnly: true,
  vncExpiresAt: '',
  seenEventIds: new Set(),
  lastSeq: 0,
  eventGapDetected: false,
  snapshotVersion: 0,
  dataAvailability: {
    quality: false,
    evidence: false,
    coverage: false,
    artifact: false,
    vnc: false,
  },
});

export function stateFromRunSummary(summary) {
  const next = emptyState();
  if (!summary) return next;

  // stages는 백엔드에서 배열로 오지만, 호출부에서 이미 처리된 state를
  // 실수로 넘기면 Map이 올 수 있다. 방어적으로 배열만 추출.
  const rawStages = summary.stages;
  const stageRows = Array.isArray(rawStages)
    ? rawStages
    : (rawStages instanceof Map ? [...rawStages.values()] : []);
  const firstStageTs = stageRows
    .map(s => Date.parse(s.first_ts || ''))
    .filter(Number.isFinite)
    .sort((a, b) => a - b)[0];
  const startedTs = Date.parse(summary.started_at || '');
  const lastTs = Date.parse(summary.last_event_at || '');

  next.firstTs = Number.isFinite(firstStageTs) ? firstStageTs : (Number.isFinite(startedTs) ? startedTs : null);
  next.lastTs = Number.isFinite(lastTs) ? lastTs : next.firstTs;
  next.runStatus = summary.status || null;
  next.pipeline = summary.pipeline_id || '';
  next.inTok = summary.kpi?.input_tokens || 0;
  next.outTok = summary.kpi?.output_tokens || 0;
  next.llmCalls = summary.kpi?.llm_calls || 0;
  next.toolCalls = summary.kpi?.tool_calls || 0;
  next.toolErr = summary.kpi?.tool_errors || 0;
  next.modelUsage = new Map((summary.usage_by_model || []).map(row => [
    `${row.provider || 'unknown'}::${row.model || 'unknown'}`,
    row,
  ]));
  next.feed = (summary.timeline || []).slice(-FEED_MAX);
  next.agentFeed = (summary.timeline || [])
    .filter(event => event?.layer === 'agent_step')
    .slice(-AGENT_TRACE_MAX);

  const quality = summary.quality || {};
  const qualityStatus = quality.status || summary.quality_status || 'not_evaluated';
  next.qualityStatus = qualityStatus;
  next.qualityScore = quality.score ?? summary.quality_score ?? null;
  next.publishable = Boolean(summary.publishable ?? quality.publishable);
  next.publishState = summary.publish_state || quality.publish_state || 'unknown';
  next.failedGate = quality.failed_gate || null;
  next.warningCount = quality.warning_count || 0;
  next.errorCount = quality.error_count || 0;
  next.repairAttempts = quality.repair_attempts || 0;

  const evidence = summary.evidence || {};
  next.evidenceItemCount = evidence.item_count || 0;
  next.evidenceMissing = evidence.missing !== false;
  next.unsupportedClaimCount = evidence.unsupported_claim_count || 0;

  const coverage = summary.coverage || {};
  next.coveragePct = coverage.percentage ?? null;
  next.coverageThreshold = coverage.threshold ?? null;
  next.coverageStatus = coverage.status || 'not_applicable';
  next.coverageReached = coverage.reached || 0;
  next.coverageExpected = coverage.expected || 0;

  const artifact = summary.artifact || {};
  next.artifactVersion = artifact.installed_version || artifact.artifact_name || null;
  next.artifactStatus = artifact.smoke_status || artifact.install_status || 'unknown';
  next.artifactReleaseTag = artifact.release_tag || null;

  const mr = summary.mr || {};
  next.mrReadiness = mr.readiness || 'unknown';
  next.mrBlockedReason = mr.blocked_reason || '';

  const vnc = summary.vnc || {};
  next.vncAvailable = Boolean(vnc.available);
  next.vncStatus = vnc.status || 'unavailable';
  next.vncSessionId = vnc.session_id || '';
  next.vncViewOnly = vnc.view_only !== false;
  next.vncExpiresAt = vnc.expires_at || '';

  next.snapshotVersion = summary.snapshot_version || 0;
  next.dataAvailability = {
    quality: Boolean(qualityStatus && qualityStatus !== 'not_evaluated'),
    evidence: !next.evidenceMissing,
    coverage: next.coverageStatus !== 'not_applicable',
    artifact: Boolean(artifact.installed_version || artifact.artifact_name),
    vnc: next.vncAvailable,
  };

  for (const row of stageRows) {
    const first = Date.parse(row.first_ts || '');
    const last = Date.parse(row.last_ts || '');
    next.stages.set(row.name, {
      layer: row.layer,
      firstTs: Number.isFinite(first) ? first : next.firstTs,
      lastTs: Number.isFinite(last) ? last : (Number.isFinite(first) ? first : next.lastTs),
      status: row.status,
      in: row.input_tokens || 0,
      out: row.output_tokens || 0,
      tools: row.tools || 0,
      progress: row.progress || {},
    });
  }

  return next;
}

export function ingest(S, e) {
  const next = {
    ...S,
    stages: new Map(S.stages || []),
    modelUsage: new Map(S.modelUsage || []),
    series: [...(S.series || [])],
    feed: [...(S.feed || [])],
    agentFeed: [...(S.agentFeed || [])],
    seenEventIds: new Set(S.seenEventIds || []),
  };
  const t = Date.parse(e.ts);
  if (Number.isFinite(t)) {
    if (!next.firstTs || t < next.firstTs) next.firstTs = t;
    if (!next.lastTs || t > next.lastTs) next.lastTs = t;
  }
  if (e.pipeline_id) next.pipeline = e.pipeline_id;
  const d = e.detail || {};

  const eid = String(e.event_id || '').trim();
  if (eid) {
    if (next.seenEventIds.has(eid)) return next;
    next.seenEventIds.add(eid);
  }

  if (typeof e.seq === 'number' && Number.isFinite(e.seq)) {
    if (e.seq > next.lastSeq + 1 && next.lastSeq > 0) {
      next.eventGapDetected = true;
    }
    if (e.seq > next.lastSeq) next.lastSeq = e.seq;
  }

  if (e.snapshot_version != null) {
    const sv = Number(e.snapshot_version) || 0;
    if (sv > next.snapshotVersion) next.snapshotVersion = sv;
  }

  if (e.layer === 'run') {
    next.runStatus = e.status;
    return next;
  }

  if (e.layer === 'stage' || e.layer === 'engine_call') {
    const prev = next.stages.get(e.stage);
    const st = prev || {layer: e.layer, firstTs: t, lastTs: t, status: e.status, in: 0, out: 0, tools: 0};
    next.stages.set(e.stage, {...st, lastTs: t, status: e.status});
    return next;
  }

  if (e.layer === 'agent_step') {
    const prev = next.stages.get(e.stage);
    const st = prev || {layer: 'agent_step', firstTs: t, lastTs: t, status: null, in: 0, out: 0, tools: 0};
    const patched = {...st, lastTs: t};
    if (d.kind === 'usage') {
      next.inTok += d.input_tokens || 0;
      next.outTok += d.output_tokens || 0;
      next.llmCalls += 1;
      patched.in += d.input_tokens || 0;
      patched.out += d.output_tokens || 0;
      const modelKey = `${d.provider || 'unknown'}::${d.model || 'unknown'}`;
      const prevModel = next.modelUsage.get(modelKey) || {
        provider: d.provider || 'unknown', model: d.model || 'unknown',
        input_tokens: 0, output_tokens: 0, calls: 0,
      };
      next.modelUsage.set(modelKey, {
        ...prevModel,
        input_tokens: prevModel.input_tokens + (d.input_tokens || 0),
        output_tokens: prevModel.output_tokens + (d.output_tokens || 0),
        calls: prevModel.calls + 1,
      });
      next.series.push({t, in: next.inTok, out: next.outTok});
    } else if (d.kind === 'tool_use') {
      next.toolCalls += 1;
      patched.tools += 1;
    } else if (d.kind === 'tool_result' && !d.ok) {
      next.toolErr += 1;
    } else if (d.kind === 'llm_retry') {
      next.retries += 1;
    } else if (d.kind === 'quality_gate_completed' || d.kind === 'quality_gate_failed') {
      const status = d.status || (d.kind === 'quality_gate_failed' ? 'fail' : 'pass');
      if (QUALITY_STATUS_VALUES.includes(status)) {
        next.qualityStatus = status;
        if (typeof d.score === 'number') next.qualityScore = d.score;
        if (d.failed_gate) next.failedGate = d.failed_gate;
        if (typeof d.warning_count === 'number') next.warningCount = d.warning_count;
        if (typeof d.error_count === 'number') next.errorCount = d.error_count;
        if (typeof d.repair_attempts === 'number') next.repairAttempts = d.repair_attempts;
        if (typeof d.publishable === 'boolean') next.publishable = d.publishable;
        if (d.publish_state) next.publishState = d.publish_state;
        next.dataAvailability.quality = true;
      }
    } else if (d.kind === 'evidence_collected' || d.kind === 'evidence_unsupported_claim') {
      if (typeof d.item_count === 'number') next.evidenceItemCount = d.item_count;
      if (typeof d.unsupported_claim_count === 'number') {
        next.unsupportedClaimCount = d.unsupported_claim_count;
      }
      if (d.item_count > 0) next.evidenceMissing = false;
      next.dataAvailability.evidence = true;
    } else if (d.kind === 'coverage_updated') {
      if (typeof d.percentage === 'number') next.coveragePct = d.percentage;
      if (typeof d.threshold === 'number') next.coverageThreshold = d.threshold;
      if (d.status) next.coverageStatus = d.status;
      if (typeof d.reached === 'number') next.coverageReached = d.reached;
      if (typeof d.expected === 'number') next.coverageExpected = d.expected;
      next.dataAvailability.coverage = true;
    } else if (d.kind === 'artifact_selected' || d.kind === 'artifact_deploy_completed' || d.kind === 'artifact_build_completed') {
      if (d.release_tag) next.artifactReleaseTag = d.release_tag;
      if (d.installed_version) next.artifactVersion = d.installed_version;
      if (d.status) next.artifactStatus = d.status;
      next.dataAvailability.artifact = true;
    } else if (d.kind === 'mr_plan_ready' || d.kind === 'mr_blocked') {
      next.mrReadiness = d.kind === 'mr_blocked' ? 'blocked' : 'ready';
      if (d.blocked_reason) next.mrBlockedReason = d.blocked_reason;
    }
    next.stages.set(e.stage, patched);
    next.feed.push(e);
    if (next.feed.length > FEED_MAX) next.feed.splice(0, next.feed.length - FEED_MAX);
    next.agentFeed.push(e);
    if (next.agentFeed.length > AGENT_TRACE_MAX) {
      next.agentFeed.splice(0, next.agentFeed.length - AGENT_TRACE_MAX);
    }
  }
  return next;
}

export function mergeRunState(S, runSummary) {
  if (!runSummary) return S;
  const summaryState = stateFromRunSummary(runSummary);
  const agentEvents = [...(summaryState.agentFeed || []), ...(S.agentFeed || [])];
  const seen = new Set();
  const agentFeed = agentEvents.filter((event) => {
    const detail = event?.detail || {};
    const key = event?.event_id || `${event?.ts}|${event?.stage}|${detail.kind || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(-AGENT_TRACE_MAX);
  return {
    ...summaryState,
    agentFeed,
    seenEventIds: new Set(S.seenEventIds || []),
    lastSeq: S.lastSeq || 0,
    eventGapDetected: S.eventGapDetected || false,
    snapshotVersion: Math.max(S.snapshotVersion || 0,
                              runSummary.snapshot_version || 0),
  };
}

export function statusBadge(status) {
  if (status === 'done') return {label: 'Done', tone: 'success'};
  if (status === 'done_with_warnings') return {label: 'Done + Warnings', tone: 'warning'};
  if (status === 'failed_quality_gate') return {label: 'Failed (Quality)', tone: 'danger'};
  if (status === 'failed') return {label: 'Failed', tone: 'danger'};
  if (status === 'partial') return {label: 'Partial', tone: 'warning'};
  if (status === 'stale') return {label: 'Stale', tone: 'warning'};
  if (status === 'cancelled') return {label: 'Cancelled', tone: 'muted'};
  if (status === 'timeout') return {label: 'Timeout', tone: 'danger'};
  if (status === 'running') return {label: 'Running', tone: 'info'};
  if (status === 'pending') return {label: 'Pending', tone: 'muted'};
  return {label: status || 'Unknown', tone: 'muted'};
}

export function qualityBadge(quality) {
  if (!quality) return {label: 'Not evaluated', tone: 'muted'};
  if (quality.status === 'pass') return {label: 'Quality Pass', tone: 'success'};
  if (quality.status === 'warning') return {label: 'Quality Warning', tone: 'warning'};
  if (quality.status === 'fail') return {label: 'Quality Fail', tone: 'danger'};
  return {label: 'Not evaluated', tone: 'muted'};
}

export function publishStateBadge(publishState) {
  if (publishState === 'publishable') return {label: 'Publishable', tone: 'success'};
  if (publishState === 'review_required') return {label: 'Review required', tone: 'warning'};
  if (publishState === 'blocked') return {label: 'Blocked', tone: 'danger'};
  return {label: 'Unknown', tone: 'muted'};
}
