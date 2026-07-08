// ManualProfilePanel — source 별 manual automation profile form.
// 2026-07-08: MCP endpoint / scenario / artifact / coverage threshold / VNC 설정 UI.

import {useEffect, useState} from 'react';

const DEFAULT_FORM = {
  enabled: false,
  mcp_endpoint_url: '',
  mcp_transport: 'sse',
  host_label: '',
  host_ip: '',
  host_port: '',
  vnc_enabled: false,
  vnc_host: '',
  vnc_port: '',
  vnc_gateway_policy: 'view_only',
  tool_allowlist: [],
  secret_refs: {},
  artifact_selector: {},
  install_profile: {},
  readiness_check: {},
  smoke_check: {},
  coverage_threshold: 70,
  failure_policy: 'block',
};

export function ManualProfilePanel({sourceId, profile, onSave, onPreflight, preflightResult, busy}) {
  const [form, setForm] = useState({...DEFAULT_FORM, ...(profile || {})});
  useEffect(() => {
    setForm({...DEFAULT_FORM, ...(profile || {})});
  }, [profile, sourceId]);

  const update = (key, value) => setForm((f) => ({...f, [key]: value}));

  const submit = (e) => {
    e.preventDefault();
    onSave && onSave(form);
  };
  const runPreflight = (e) => {
    e.preventDefault();
    onPreflight && onPreflight();
  };

  return (
    <form className="manual-profile-panel" onSubmit={submit}>
      <div className="manual-profile-panel__row">
        <label>
          <input
            type="checkbox"
            checked={Boolean(form.enabled)}
            onChange={(e) => update('enabled', e.target.checked)}
          /> 활성화
        </label>
        <label>
          <input
            type="checkbox"
            checked={Boolean(form.vnc_enabled)}
            onChange={(e) => update('vnc_enabled', e.target.checked)}
          /> VNC 모니터링
        </label>
      </div>
      <div className="manual-profile-panel__row">
        <label>
          MCP endpoint URL
          <input
            type="text"
            value={form.mcp_endpoint_url || ''}
            onChange={(e) => update('mcp_endpoint_url', e.target.value)}
            placeholder="http://mcp.internal:8765/sse"
          />
        </label>
        <label>
          Transport
          <select
            value={form.mcp_transport || 'sse'}
            onChange={(e) => update('mcp_transport', e.target.value)}
          >
            <option value="sse">sse</option>
            <option value="stdio">stdio</option>
            <option value="websocket">websocket</option>
          </select>
        </label>
      </div>
      <div className="manual-profile-panel__row">
        <label>
          Host label
          <input
            type="text"
            value={form.host_label || ''}
            onChange={(e) => update('host_label', e.target.value)}
          />
        </label>
        <label>
          Host IP
          <input
            type="text"
            value={form.host_ip || ''}
            onChange={(e) => update('host_ip', e.target.value)}
            placeholder="10.0.0.12"
          />
        </label>
        <label>
          Host port
          <input
            type="number"
            value={form.host_port || ''}
            onChange={(e) => update('host_port', e.target.value)}
          />
        </label>
      </div>
      <div className="manual-profile-panel__row">
        <label>
          VNC host
          <input
            type="text"
            value={form.vnc_host || ''}
            onChange={(e) => update('vnc_host', e.target.value)}
            disabled={!form.vnc_enabled}
          />
        </label>
        <label>
          VNC port
          <input
            type="number"
            value={form.vnc_port || ''}
            onChange={(e) => update('vnc_port', e.target.value)}
            disabled={!form.vnc_enabled}
          />
        </label>
        <label>
          VNC policy
          <select
            value={form.vnc_gateway_policy || 'view_only'}
            onChange={(e) => update('vnc_gateway_policy', e.target.value)}
            disabled={!form.vnc_enabled}
          >
            <option value="view_only">view_only</option>
            <option value="disabled">disabled</option>
          </select>
        </label>
      </div>
      <div className="manual-profile-panel__row">
        <label>
          Tool allowlist (comma separated)
          <input
            type="text"
            value={Array.isArray(form.tool_allowlist) ? form.tool_allowlist.join(', ') : ''}
            onChange={(e) => update('tool_allowlist',
              e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
            placeholder="screenshot, click, hotkey"
          />
        </label>
        <label>
          Coverage threshold (%)
          <input
            type="number"
            min="0"
            max="100"
            value={form.coverage_threshold ?? 70}
            onChange={(e) => update('coverage_threshold', parseInt(e.target.value, 10))}
          />
        </label>
        <label>
          Failure policy
          <select
            value={form.failure_policy || 'block'}
            onChange={(e) => update('failure_policy', e.target.value)}
          >
            <option value="block">block</option>
            <option value="review_required">review_required</option>
            <option value="continue_with_warnings">continue_with_warnings</option>
          </select>
        </label>
      </div>
      <div className="manual-profile-panel__row">
        <button type="submit" disabled={busy}>저장</button>
        <button type="button" onClick={runPreflight} disabled={busy}>Preflight</button>
      </div>
      {preflightResult && (
        <div className={`manual-profile-panel__preflight ${preflightResult.ok ? 'ok' : 'fail'}`}>
          {preflightResult.ok ? 'Preflight OK' : 'Preflight failed'}
          {preflightResult.errors && preflightResult.errors.length > 0 && (
            <ul>
              {preflightResult.errors.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          )}
          {preflightResult.warnings && preflightResult.warnings.length > 0 && (
            <ul>
              {preflightResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
        </div>
      )}
    </form>
  );
}
