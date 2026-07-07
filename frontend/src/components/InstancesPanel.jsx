import {Plus, Save} from 'lucide-react';
import {blankInstance, fieldValue} from '../lib/defaults.js';

export function InstancesPanel({instances, form, onChange, onSave, onToggleEnabled, busy, message}) {
  const set = (key, value) => onChange({...form, [key]: value});
  const isGithub = (form.kind || 'gitlab') === 'github';
  return <div className="editor instances">
    <div className="editorHead">
      <div><h2>SCM 인스턴스</h2><p>사내 GitLab · gitlab.com · github.com — 인스턴스 단위 공용 토큰</p></div>
    </div>
    <div className="tableScroll">
      <table>
        <thead><tr><th>이름</th><th>종류</th><th>base_url</th><th>토큰</th><th>상태</th><th></th></tr></thead>
        <tbody>
          {instances.length ? instances.map(i => <tr key={i.id}>
            <td className="mono strong clickable" onClick={() => onChange({...i, token: ''})}>{i.label || i.id}</td>
            <td>{i.kind}</td>
            <td>{i.base_url || '(기본 URL)'}</td>
            <td>{i.has_token ? '있음' : '없음'}</td>
            <td><span className={`stageState ${i.enabled ? 'done' : 'idle'}`}><span />{i.enabled ? '활성' : '비활성'}</span></td>
            <td><button type="button" className="iconTextBtn" onClick={() => onToggleEnabled(i)}>{i.enabled ? '비활성화' : '활성화'}</button></td>
          </tr>) : <tr><td colSpan={6} className="emptyCell">등록된 인스턴스 없음 — 소스 저장 시 자동 생성되거나 여기서 직접 등록</td></tr>}
        </tbody>
      </table>
    </div>
    <form onSubmit={ev => { ev.preventDefault(); onSave(); }}>
      <div className="formGrid">
        <label>식별자(ID)<input value={fieldValue(form, 'id')} onChange={e => set('id', e.target.value)} placeholder="github-com" /></label>
        <label>종류<select value={fieldValue(form, 'kind') || 'gitlab'} onChange={e => set('kind', e.target.value)}>
          <option value="gitlab">gitlab</option>
          <option value="github">github</option>
        </select></label>
        <label>이름<input value={fieldValue(form, 'label')} onChange={e => set('label', e.target.value)} /></label>
        <label>{isGithub ? 'URL (비우면 github.com)' : 'Base URL'}<input value={fieldValue(form, 'base_url')} onChange={e => set('base_url', e.target.value)} placeholder={isGithub ? '' : 'https://gitlab.com'} /></label>
        <label>토큰 헤더<input value={fieldValue(form, 'token_header') || 'PRIVATE-TOKEN'} onChange={e => set('token_header', e.target.value)} /></label>
        <label>토큰<input value={fieldValue(form, 'token')} onChange={e => set('token', e.target.value)} type="password" placeholder="인스턴스 공용 토큰" /></label>
      </div>
      <div className="panelActions">
        <button type="button" className="iconTextBtn" onClick={() => onChange(blankInstance)}><Plus size={15} />신규</button>
        <button className="primaryBtn" disabled={busy}><Save size={15} />인스턴스 저장</button>
      </div>
    </form>
    {message && <p className="formMessage">{message}</p>}
  </div>;
}
