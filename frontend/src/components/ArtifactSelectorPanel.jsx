// ArtifactSelectorPanel — release/tag/build 기반 artifact preflight.

import {useState} from 'react';

export function ArtifactSelectorPanel({preflightResult, onPreflight, busy}) {
  const [releaseTag, setReleaseTag] = useState('');
  const [branch, setBranch] = useState('');
  const [build, setBuild] = useState('');

  const submit = (e) => {
    e.preventDefault();
    onPreflight && onPreflight({release_tag: releaseTag, branch, build});
  };

  return (
    <form className="artifact-selector-panel" onSubmit={submit}>
      <div className="artifact-selector-panel__row">
        <label>Release tag
          <input type="text" value={releaseTag} onChange={(e) => setReleaseTag(e.target.value)} placeholder="v1.8.0" />
        </label>
        <label>Branch
          <input type="text" value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="main" />
        </label>
        <label>Build ref
          <input type="text" value={build} onChange={(e) => setBuild(e.target.value)} placeholder="sha or build id" />
        </label>
      </div>
      <button type="submit" disabled={busy}>Preflight</button>
      {preflightResult && (
        <div className={`artifact-selector-panel__result ${preflightResult.ok ? 'ok' : 'fail'}`}>
          {preflightResult.selected_artifact ? (
            <div>
              <div><strong>Selected:</strong> {preflightResult.selected_artifact.release_tag || '—'}</div>
              <div><strong>Type:</strong> {preflightResult.selected_artifact.installer_type || 'unknown'}</div>
              <div><strong>Checksum:</strong> {preflightResult.selected_artifact.checksum_available ? 'available' : 'missing'}</div>
              <div><strong>Install command preview:</strong> <code>{preflightResult.selected_artifact.install_command_preview || '—'}</code></div>
            </div>
          ) : (
            <div>선택된 artifact 가 없습니다.</div>
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
