// ScenarioEditor — scenario set 작성/검증/버전 관리.
// 2026-07-08: lint + activate 지원, raw secret 검출.

import {useEffect, useState} from 'react';

const SECRET_FIELDS = ['password', 'token', 'secret', 'api_key'];

export function ScenarioEditor({scenarios, onCreate, onUpdate, onActivate, onDelete, onLint, lintResult, busy}) {
  const [editing, setEditing] = useState(null);
  const [json, setJson] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    if (editing) {
      setJson(JSON.stringify(editing.scenarios || {}, null, 2));
    }
  }, [editing]);

  const startNew = () => {
    setEditing({id: null, name: 'default', version: 1, status: 'draft', scenarios: {}});
  };
  const startEdit = (s) => {
    setEditing(s);
  };
  const onChange = (raw) => {
    setJson(raw);
    try {
      const parsed = JSON.parse(raw);
      setEditing((cur) => ({...(cur || {}), scenarios: parsed}));
      setError(null);
    } catch (e) {
      setError('JSON parse error: ' + e.message);
    }
  };

  const save = () => {
    if (!editing) return;
    onUpdate && onUpdate(editing);
  };
  const createNew = () => {
    if (!editing) return;
    onCreate && onCreate(editing);
  };

  return (
    <div className="scenario-editor">
      <div className="scenario-editor__list">
        <h4>Scenario sets</h4>
        <button type="button" onClick={startNew}>+ 새 set</button>
        <ul>
          {(scenarios || []).map((s) => (
            <li key={s.id} className={editing?.id === s.id ? 'active' : ''}>
              <button type="button" onClick={() => startEdit(s)}>
                {s.name} <span className={`pill pill--${s.status === 'active' ? 'success' : 'muted'}`}>{s.status}</span> v{s.version}
              </button>
              {s.status !== 'active' && (
                <button type="button" onClick={() => onActivate && onActivate(s)}>activate</button>
              )}
              <button type="button" onClick={() => onDelete && onDelete(s)}>delete</button>
            </li>
          ))}
        </ul>
      </div>
      <div className="scenario-editor__detail">
        {editing ? (
          <>
            <div className="scenario-editor__row">
              <label>name <input
                type="text"
                value={editing.name || ''}
                onChange={(e) => setEditing({...editing, name: e.target.value})}
              /></label>
              <label>version <input
                type="number"
                value={editing.version || 1}
                onChange={(e) => setEditing({...editing, version: parseInt(e.target.value, 10)})}
              /></label>
            </div>
            <textarea
              value={json}
              onChange={(e) => onChange(e.target.value)}
              rows={20}
              spellCheck={false}
            />
            {error && <div className="scenario-editor__error">{error}</div>}
            <div className="scenario-editor__row">
              <button type="button" onClick={() => onLint && onLint(editing)} disabled={busy}>Lint</button>
              {editing.id ? (
                <button type="button" onClick={save} disabled={busy}>저장</button>
              ) : (
                <button type="button" onClick={createNew} disabled={busy}>생성</button>
              )}
            </div>
            {lintResult && (
              <div className={`scenario-editor__lint ${lintResult.ok ? 'ok' : 'fail'}`}>
                {lintResult.ok
                  ? `Lint OK — scenarios ${lintResult.scenario_count ?? '?'}`
                  : `Lint failed — ${lintResult.error_count} errors`}
                {lintResult.errors && lintResult.errors.length > 0 && (
                  <ul>
                    {lintResult.errors.map((e, i) => (
                      <li key={i}>
                        {e.id || e.index || `error-${i}`}: {e.code} — {e.message}
                      </li>
                    ))}
                  </ul>
                )}
                {lintResult.errors && lintResult.errors.some((e) => e.code === 'raw_secret_not_allowed') && (
                  <div className="scenario-editor__warning">
                    raw secret 가 발견됐습니다. secret_ref 만 사용하세요.
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="empty-state">왼쪽에서 set 을 선택하거나 새로 만드세요.</div>
        )}
      </div>
    </div>
  );
}
