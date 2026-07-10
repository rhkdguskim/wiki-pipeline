import {Save, ShieldCheck, XCircle} from 'lucide-react';
import {fieldValue} from '../lib/defaults.js';
import {TriggerButton} from './TriggerButton.jsx';

// 소스 필드 정의 — 개요(공용 저장소 연결)와 docu-automation(테마/브랜치/doc_dir)이
// 같은 컴포넌트를 서로 다른 field 집합으로 재사용한다.
//   공용  : id/label/kind/project_id/url/token_header/token/owner_email/enabled
//   docu  : dev_branch/release_branch/doc_dir/themes
// 저장은 어느 쪽이든 동일한 소스 upsert 로 나가므로 form 은 하나를 공유한다.
export const SOURCE_FIELD_GROUPS = {
  common: ['id', 'label', 'kind', 'project_id', 'url', 'token_header', 'token', 'owner_email', 'enabled'],
  docu: ['dev_branch', 'release_branch', 'doc_dir', 'themes'],
};

function renderField(fk, {form, set, isGithub}) {
  switch (fk) {
    case 'id':
      return <label key={fk}>식별자(ID)<input value={fieldValue(form, 'id')} onChange={e => set('id', e.target.value)} placeholder="sw-rcs" /></label>;
    case 'label':
      return <label key={fk}>이름<input value={fieldValue(form, 'label')} onChange={e => set('label', e.target.value)} placeholder="SW RCS" /></label>;
    case 'kind':
      return <label key={fk}>종류<select value={fieldValue(form, 'kind') || 'gitlab'} onChange={e => set('kind', e.target.value)}>
        <option value="gitlab">gitlab</option>
        <option value="github">github</option>
      </select></label>;
    case 'project_id':
      return <label key={fk}>{isGithub ? '레포 (owner/repo)' : '프로젝트 ID'}<input value={fieldValue(form, 'project_id')} onChange={e => set('project_id', e.target.value)} placeholder={isGithub ? 'owner/repo' : '947'} /></label>;
    case 'url':
      return <label className="span2" key={fk}>{isGithub ? 'URL (비우면 github.com)' : 'GitLab URL'}<input value={fieldValue(form, 'url')} onChange={e => set('url', e.target.value)} placeholder={isGithub ? 'https://github.com (기본)' : 'http://wish.mirero.co.kr'} /></label>;
    case 'dev_branch':
      return <label key={fk}>dev 브랜치<input value={fieldValue(form, 'dev_branch')} onChange={e => set('dev_branch', e.target.value)} placeholder="develop" /></label>;
    case 'release_branch':
      return <label key={fk}>release 브랜치<input value={fieldValue(form, 'release_branch')} onChange={e => set('release_branch', e.target.value)} placeholder="비우면 default branch" /></label>;
    case 'doc_dir':
      return <label className="span2" key={fk}>문서 산출 경로 (doc_dir)<input value={fieldValue(form, 'doc_dir')} onChange={e => set('doc_dir', e.target.value)} placeholder="docs/ (비우면 기본값)" /></label>;
    case 'themes':
      return <label className="span2" key={fk}>테마<input value={fieldValue(form, 'themes')} onChange={e => set('themes', e.target.value)} placeholder="intro,requirements,architecture-overview" /></label>;
    case 'owner_email':
      return <label key={fk}>담당자 이메일<input value={fieldValue(form, 'owner_email')} onChange={e => set('owner_email', e.target.value)} placeholder="실패 알림 수신자" /></label>;
    case 'token_header':
      return <label key={fk}>토큰 헤더<input value={fieldValue(form, 'token_header') || 'PRIVATE-TOKEN'} onChange={e => set('token_header', e.target.value)} /></label>;
    case 'token':
      return <label key={fk}>토큰<input value={fieldValue(form, 'token')} onChange={e => set('token', e.target.value)} placeholder="저장 시에만 사용, 응답에는 표시 안 됨" type="password" autoComplete="off" spellCheck={false} aria-label="SCM 토큰" /></label>;
    case 'enabled':
      return <label className="checkRow" key={fk}><input type="checkbox" checked={form.enabled !== false} onChange={e => set('enabled', e.target.checked)} />활성 (배치 대상)</label>;
    default:
      return null;
  }
}

export function SourceEditor({
  form, onChange, onSave, onVerify, onTrigger, busy, message, verifyResult,
  title = '소스 등록',
  fields = null,          // null 이면 전체(레거시), 아니면 표시할 필드 키 배열
  showTrigger = true,
}) {
  const set = (key, value) => onChange({...form, [key]: value});
  const isGithub = (form.kind || 'gitlab') === 'github';
  // form 으로 source-like 객체를 합성해서 trigger button 에 넘긴다.
  const sourceLike = form.id ? {id: form.id, label: form.label || form.id, enabled: form.enabled !== false} : null;

  // fields 미지정 시 기존 전체 폼 순서를 그대로 유지(하위 호환).
  const shown = fields || [
    ...SOURCE_FIELD_GROUPS.common.slice(0, 5),   // id..url
    'dev_branch', 'release_branch', 'doc_dir', 'themes',
    'owner_email', 'token_header', 'token', 'enabled',
  ];

  return <form className="editor" onSubmit={ev => { ev.preventDefault(); onSave(); }}>
    <input
      type="text"
      name="username"
      autoComplete="username"
      tabIndex={-1}
      aria-hidden="true"
      style={{position: 'absolute', left: '-9999px', width: 1, height: 1, opacity: 0}}
      readOnly
    />
    <div className="editorHead">
      <h2>{title}</h2>
      <div className="panelActions">
        <button type="button" className="iconTextBtn" disabled={busy || !form.id} onClick={onVerify} title="토큰·접근 검증 + 자동 조회 (compare dry-run)"><ShieldCheck size={15} />검증</button>
        {showTrigger && sourceLike && <TriggerButton source={sourceLike} onTrigger={onTrigger} busy={busy} disabled={!form.enabled && form.enabled !== undefined} size="md" />}
        <button className="primaryBtn" disabled={busy}><Save size={15} />저장</button>
      </div>
    </div>
    <div className="formGrid">
      {shown.map(fk => renderField(fk, {form, set, isGithub}))}
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
