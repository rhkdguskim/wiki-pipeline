import {Save} from 'lucide-react';
import {defaultDocTarget, fieldValue} from '../lib/defaults.js';

export function DocsHubPanel({target, onChange, onSave, busy, message, embedded}) {
  const form = target || defaultDocTarget;
  const set = (key, value) => onChange({...form, [key]: value});
  return <form className={embedded ? 'docsHubEmbedded' : 'editor docsTarget'} onSubmit={ev => { ev.preventDefault(); onSave(); }}>
    <input
      type="text"
      name="username"
      autoComplete="username"
      tabIndex={-1}
      aria-hidden="true"
      style={{position: 'absolute', left: '-9999px', width: 1, height: 1, opacity: 0}}
      readOnly
    />
    {!embedded && <div className="editorHead">
      <div><h2>문서 허브 대상</h2><p>생성 산출물 MR 대상: product-common</p></div>
      <button className="primaryBtn" disabled={busy}><Save size={15} />저장</button>
    </div>}
    {embedded && <div className="panelActions" style={{justifyContent: 'flex-end', marginBottom: 10}}>
      <button className="primaryBtn" disabled={busy}><Save size={15} />저장</button>
    </div>}
    <div className="formGrid">
      <label>식별자(ID)<input value={fieldValue(form, 'id') || 'product-common'} onChange={e => set('id', e.target.value)} /></label>
      <label>이름<input value={fieldValue(form, 'label') || 'product-common'} onChange={e => set('label', e.target.value)} /></label>
      <label>종류<select value={fieldValue(form, 'kind') || 'gitlab'} onChange={e => set('kind', e.target.value)}>
        <option value="gitlab">gitlab</option>
        <option value="github">github</option>
      </select></label>
      <label className="span2">프로젝트 URL<input value={fieldValue(form, 'url')} onChange={e => set('url', e.target.value)} /></label>
      <label>프로젝트 ID<input value={fieldValue(form, 'project_id')} onChange={e => set('project_id', e.target.value)} placeholder="숫자 id 알면 입력" /></label>
      <label>프로젝트 경로<input value={fieldValue(form, 'project_path')} onChange={e => set('project_path', e.target.value)} /></label>
      <label>default 브랜치<input value={fieldValue(form, 'default_branch') || 'master'} onChange={e => set('default_branch', e.target.value)} /></label>
      <label>토큰 헤더<input value={fieldValue(form, 'token_header') || 'PRIVATE-TOKEN'} onChange={e => set('token_header', e.target.value)} /></label>
      <label className="span2">MR 토큰<input value={fieldValue(form, 'token')} onChange={e => set('token', e.target.value)} type="password" autoComplete="off" spellCheck={false} aria-label="MR 토큰" placeholder="product-common MR 생성/브랜치 push용" /></label>
      <label className="checkRow"><input type="checkbox" checked={form.enabled === true} onChange={e => set('enabled', e.target.checked)} />MR 제출 활성</label>
    </div>
    {message && <p className="formMessage">{message}</p>}
  </form>;
}
