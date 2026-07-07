import {Play, Save, ShieldCheck, XCircle} from 'lucide-react';
import {fieldValue} from '../lib/defaults.js';

export function SourceEditor({form, onChange, onSave, onVerify, onTrigger, busy, message, verifyResult}) {
  const set = (key, value) => onChange({...form, [key]: value});
  const isGithub = (form.kind || 'gitlab') === 'github';
  return <form className="editor" onSubmit={ev => { ev.preventDefault(); onSave(); }}>
    <div className="editorHead">
      <h2>소스 등록</h2>
      <div className="panelActions">
        <button type="button" className="iconTextBtn" disabled={busy || !form.id} onClick={onVerify} title="토큰·접근 검증 + 자동 조회 (compare dry-run)"><ShieldCheck size={15} />검증</button>
        <button type="button" className="iconTextBtn" disabled={busy || !form.id} onClick={() => onTrigger(form.id)} title="지금 배치 실행 (auto: 포인터 없으면 init, 있으면 diff)"><Play size={15} />실행</button>
        <button className="primaryBtn" disabled={busy}><Save size={15} />저장</button>
      </div>
    </div>
    <div className="formGrid">
      <label>식별자(ID)<input value={fieldValue(form, 'id')} onChange={e => set('id', e.target.value)} placeholder="sw-rcs" /></label>
      <label>이름<input value={fieldValue(form, 'label')} onChange={e => set('label', e.target.value)} placeholder="SW RCS" /></label>
      <label>종류<select value={fieldValue(form, 'kind') || 'gitlab'} onChange={e => set('kind', e.target.value)}>
        <option value="gitlab">gitlab</option>
        <option value="github">github</option>
      </select></label>
      <label>{isGithub ? '레포 (owner/repo)' : '프로젝트 ID'}<input value={fieldValue(form, 'project_id')} onChange={e => set('project_id', e.target.value)} placeholder={isGithub ? 'owner/repo' : '947'} /></label>
      <label className="span2">{isGithub ? 'URL (비우면 github.com)' : 'GitLab URL'}<input value={fieldValue(form, 'url')} onChange={e => set('url', e.target.value)} placeholder={isGithub ? 'https://github.com (기본)' : 'http://wish.mirero.co.kr'} /></label>
      <label>dev 브랜치<input value={fieldValue(form, 'dev_branch')} onChange={e => set('dev_branch', e.target.value)} placeholder="develop" /></label>
      <label>release 브랜치<input value={fieldValue(form, 'release_branch')} onChange={e => set('release_branch', e.target.value)} placeholder="비우면 default branch" /></label>
      <label className="span2">테마<input value={fieldValue(form, 'themes')} onChange={e => set('themes', e.target.value)} /></label>
      <label>담당자 이메일<input value={fieldValue(form, 'owner_email')} onChange={e => set('owner_email', e.target.value)} placeholder="실패 알림 수신자" /></label>
      <label>스케줄 cron<input value={fieldValue(form, 'schedule_cron')} onChange={e => set('schedule_cron', e.target.value)} placeholder="비우면 평일 20:00" /></label>
      <label>토큰 헤더<input value={fieldValue(form, 'token_header') || 'PRIVATE-TOKEN'} onChange={e => set('token_header', e.target.value)} /></label>
      <label>토큰<input value={fieldValue(form, 'token')} onChange={e => set('token', e.target.value)} placeholder="저장 시에만 사용, 응답에는 표시 안 됨" type="password" /></label>
      <label className="checkRow"><input type="checkbox" checked={form.enabled !== false} onChange={e => set('enabled', e.target.checked)} />활성 (배치 대상)</label>
    </div>
    {verifyResult && <div className={verifyResult.verified ? 'verifyBox ok' : 'verifyBox bad'}>
      {verifyResult.verified ? <>
        <p><ShieldCheck size={13} /> 검증 성공 — <b>{verifyResult.name}</b> ({verifyResult.namespace_path})</p>
        <p>default branch <b>{verifyResult.default_branch}</b> · HEAD <span className="mono">{(verifyResult.head_sha || '').slice(0, 12)}</span></p>
        <p>브랜치 {verifyResult.branches?.length || 0}개: {(verifyResult.branches || []).slice(0, 8).join(', ')}{(verifyResult.branches || []).length > 8 ? ' …' : ''}</p>
      </> : <p><XCircle size={13} /> 검증 실패: {verifyResult.error}</p>}
    </div>}
    {message && <p className="formMessage">{message}</p>}
  </form>;
}
