import {Play, Plus, Search, ShieldCheck} from 'lucide-react';
import {DocsHubPanel} from '../components/DocsHubPanel.jsx';
import {SourceEditor} from '../components/SourceEditor.jsx';
import {InstancesPanel} from '../components/InstancesPanel.jsx';

export function SourcesPage({
  visibleSources, query, onQueryChange, onNewSource, onOpenWizard, onSelectSource,
  sourceForm, onSourceFormChange, onSaveSource, onVerifySource, onTriggerSource,
  saveBusy, saveMessage, verifyResult,
  targetForm, onTargetFormChange, onSaveTarget,
  instances, instanceForm, onInstanceFormChange, onSaveInstance,
}) {
  return <section className="panel">
    <div className="panelHead">
      <h2>Source Registry</h2>
      <div className="panelActions">
        <button className="primaryBtn" onClick={onOpenWizard}><Plus size={15} />소스 추가</button>
        <button className="iconTextBtn" onClick={onNewSource}>수정 폼 초기화</button>
        <label className="search"><Search size={15} /><input value={query} onChange={e => onQueryChange(e.target.value)} placeholder="source 검색" /></label>
      </div>
    </div>
    <div className="registryLayout">
      <div className="sourceGrid">
        {visibleSources.map(s => <article className="sourceCard" key={s.id} onClick={() => onSelectSource(s)}>
          <div><strong>{s.label}</strong><span>{s.enabled ? 'enabled' : 'disabled'} · {s.kind} · project {s.project_id}</span></div>
          <p>{s.url}</p>
          {!s.enabled && s.disabled_reason && <p className="errText">{s.disabled_reason}</p>}
          <dl>
            <dt>runs</dt><dd>{s.runs}</dd>
            <dt>dev</dt><dd>{s.dev_branch || '-'}</dd>
            <dt>release</dt><dd>{s.release_branch || '-'}</dd>
            <dt>sha</dt><dd className="mono">{s.last_processed_sha ? s.last_processed_sha.slice(0, 12) : '-'}</dd>
          </dl>
          <div className="tagRow">{(s.themes || []).map(t => <span key={t}>{t}</span>)}</div>
          <div className="panelActions">
            <button type="button" className="iconTextBtn" disabled={!s.enabled} onClick={e => { e.stopPropagation(); onTriggerSource(s.id); }} title={s.enabled ? '지금 배치 실행' : s.disabled_reason || '비활성 소스'}>
              <Play size={14} />실행
            </button>
            <button type="button" className="iconTextBtn" onClick={e => { e.stopPropagation(); onVerifySource(s.id); }} title="토큰·접근 검증">
              <ShieldCheck size={14} />검증
            </button>
          </div>
        </article>)}
      </div>
      <div className="registrySide">
        <DocsHubPanel target={targetForm} onChange={onTargetFormChange} onSave={onSaveTarget} busy={saveBusy} message={saveMessage} />
        <SourceEditor form={sourceForm} onChange={onSourceFormChange} onSave={onSaveSource} onVerify={onVerifySource} onTrigger={onTriggerSource} busy={saveBusy} message={saveMessage} verifyResult={verifyResult} />
        <InstancesPanel instances={instances} form={instanceForm} onChange={onInstanceFormChange} onSave={onSaveInstance} busy={saveBusy} message={saveMessage} />
      </div>
    </div>
  </section>;
}
