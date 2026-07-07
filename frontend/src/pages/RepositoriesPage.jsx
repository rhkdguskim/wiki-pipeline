import {Plus, Search, Server} from 'lucide-react';
import {InstancesPanel} from '../components/InstancesPanel.jsx';
import {SourcesTable} from '../components/SourcesTable.jsx';
import {DocsHubPanel} from '../components/DocsHubPanel.jsx';
import {EmptyState} from '../components/EmptyState.jsx';
import {PageHeader} from '../components/PageHeader.jsx';
import {LoadingBlock, ErrorBanner} from '../components/QueryState.jsx';

export function RepositoriesPage({
  instances, instanceForm, onInstanceFormChange, onSaveInstance, onToggleInstanceEnabled,
  sources, query, onQueryChange, onOpenWizard, onOpenDetail,
  onVerifySource, onTriggerSource, onEditSource, onToggleSourceEnabled,
  targetForm, onTargetFormChange, onSaveTarget,
  busy, message, isLoading, isError, error, onRetry,
}) {
  const visibleSources = sources.filter(s => !query || `${s.label} ${s.project_id} ${s.id}`.toLowerCase().includes(query.toLowerCase()));

  const hasSources = sources.length > 0;

  return <div>
    <PageHeader
      title="저장소"
      description="SCM 인스턴스와 소스를 등록·관리합니다"
      actions={(isLoading || hasSources) && <button className="primaryBtn" onClick={onOpenWizard}><Plus size={15} />소스 추가</button>}
    />

    {isLoading && <LoadingBlock />}
    {isError && <ErrorBanner message={error?.message} onRetry={onRetry} />}

    {!isLoading && !isError && <>
      <section className="panel">
        <div className="panelHead"><h2>SCM 인스턴스</h2><p className="panelHint">사내 GitLab · gitlab.com · github.com — 인스턴스 단위 공용 토큰</p></div>
        <InstancesPanel instances={instances} form={instanceForm} onChange={onInstanceFormChange} onSave={onSaveInstance} onToggleEnabled={onToggleInstanceEnabled} busy={busy} message={message} />
      </section>

      <section className="panel" style={{marginTop: 14}}>
        <div className="panelHead">
          <h2>소스</h2>
          {hasSources && <label className="search"><Search size={15} /><input value={query} onChange={e => onQueryChange(e.target.value)} placeholder="소스 검색" /></label>}
        </div>
        {hasSources
          ? <SourcesTable sources={visibleSources} onOpenDetail={onOpenDetail} onVerify={onVerifySource} onTrigger={onTriggerSource} onEdit={onEditSource} onToggleEnabled={onToggleSourceEnabled} />
          : <EmptyState icon={Server} title="등록된 소스가 없습니다" description="GitLab 또는 GitHub 저장소를 연결해 문서 자동화를 시작하세요" actionLabel="+ 소스 추가" onAction={onOpenWizard} />}
      </section>

      <section className="panel" style={{marginTop: 14}}>
        <div className="panelHead"><h2>문서 허브 설정</h2><p className="panelHint">생성된 문서를 MR로 제출할 대상 저장소 (product-common)</p></div>
        <DocsHubPanel target={targetForm} onChange={onTargetFormChange} onSave={onSaveTarget} busy={busy} message={message} />
      </section>
    </>}
  </div>;
}
