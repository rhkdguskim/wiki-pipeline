import {Plus, Save} from 'lucide-react';
import {blankInstance, fieldValue} from '../lib/defaults.js';

export function InstancesPanel({instances, form, onChange, onSave, busy, message}) {
  const set = (key, value) => onChange({...form, [key]: value});
  const isGithub = (form.kind || 'gitlab') === 'github';
  return <div className="editor instances">
    <div className="editorHead">
      <div><h2>SCM Instances</h2><p>사내 GitLab · gitlab.com · github.com — 인스턴스 공용 토큰</p></div>
    </div>
    <div className="miniList">
      {instances.length ? instances.map(i => <span key={i.id} className="clickable" onClick={() => onChange({...i, token: ''})}>
        <b>{i.label || i.id}</b><em>{i.kind}{i.base_url ? ` · ${i.base_url}` : ''} · {i.has_token ? '토큰 있음' : '토큰 없음'}{i.enabled ? '' : ' · 비활성'}</em>
      </span>) : <small>등록된 인스턴스 없음 — 소스 저장 시 자동 생성되거나 여기서 직접 등록</small>}
    </div>
    <form onSubmit={ev => { ev.preventDefault(); onSave(); }}>
      <div className="formGrid">
        <label>ID<input value={fieldValue(form, 'id')} onChange={e => set('id', e.target.value)} placeholder="github-com" /></label>
        <label>Kind<select value={fieldValue(form, 'kind') || 'gitlab'} onChange={e => set('kind', e.target.value)}>
          <option value="gitlab">gitlab</option>
          <option value="github">github</option>
        </select></label>
        <label>Label<input value={fieldValue(form, 'label')} onChange={e => set('label', e.target.value)} /></label>
        <label>{isGithub ? 'URL (비우면 github.com)' : 'Base URL'}<input value={fieldValue(form, 'base_url')} onChange={e => set('base_url', e.target.value)} placeholder={isGithub ? '' : 'https://gitlab.com'} /></label>
        <label>Token header<input value={fieldValue(form, 'token_header') || 'PRIVATE-TOKEN'} onChange={e => set('token_header', e.target.value)} /></label>
        <label>Token<input value={fieldValue(form, 'token')} onChange={e => set('token', e.target.value)} type="password" placeholder="인스턴스 공용 토큰" /></label>
      </div>
      <div className="panelActions">
        <button type="button" className="iconTextBtn" onClick={() => onChange(blankInstance)}><Plus size={15} />신규</button>
        <button className="primaryBtn" disabled={busy}><Save size={15} />인스턴스 저장</button>
      </div>
    </form>
    {message && <p className="formMessage">{message}</p>}
  </div>;
}
