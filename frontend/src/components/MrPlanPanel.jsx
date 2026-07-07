import {FileText, GitBranch, GitPullRequest, RefreshCw} from 'lucide-react';
import {fmtNum} from '../lib/format.js';

export function MrPlanPanel({plan, busy, message, onSubmit, onRefresh}) {
  if (!plan) return <div className="mrBox emptyMini">MR 계획 대기</div>;
  const blocked = !plan.can_submit;
  return <div className="mrBox">
    <div className="mrHead">
      <div>
        <span className="contextLabel">product-common MR</span>
        <strong>{plan.file_count} files · {fmtNum(plan.total_bytes)}B</strong>
      </div>
      <button className="iconBtn" onClick={onRefresh} title="MR 계획 새로고침"><RefreshCw size={15} /></button>
    </div>
    <div className="mrMeta">
      <span><GitBranch size={13} />{plan.branch_name}</span>
      <span><FileText size={13} />{plan.branch_role}/{plan.target?.default_branch}</span>
    </div>
    <div className="miniList">
      {plan.files.slice(0, 4).map(f => <span key={f.target_path}><b>{f.target_path}</b><em>{fmtNum(f.size)}B</em></span>)}
    </div>
    {!!plan.warnings?.length && <div className="warningList">{plan.warnings.slice(0, 3).map((w, i) => <p key={i}>{w}</p>)}</div>}
    <button className="primaryBtn fullBtn" disabled={busy || blocked} onClick={onSubmit}>
      <GitPullRequest size={15} />MR 요청
    </button>
    <small className={blocked ? 'blockedText' : 'readyText'}>
      {blocked ? (plan.target?.has_token ? 'target 비활성 또는 파일 없음' : '토큰 필요') : '제출 준비 완료'}
    </small>
    {message && <p className="formMessage">{message}</p>}
  </div>;
}
