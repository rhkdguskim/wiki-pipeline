import {Plus, Search, Server} from 'lucide-react';
import {SourcesTable} from '../components/SourcesTable.jsx';
import {EmptyState} from '../components/EmptyState.jsx';
import {PageHeader} from '../components/PageHeader.jsx';
import {LoadingBlock, ErrorBanner} from '../components/QueryState.jsx';

export function RepositoriesPage({
  sources, query, onQueryChange, onOpenWizard, onOpenDetail,
  onVerifySource, onTriggerSource, onToggleSourceEnabled, onDeleteSource,
  busy, message, isLoading, isError, error, onRetry,
}) {
  const visibleSources = sources.filter(s => !query || `${s.label} ${s.project_id} ${s.id}`.toLowerCase().includes(query.toLowerCase()));

  const hasSources = sources.length > 0;

  return <div>
    <PageHeader
      eyebrow="SOURCES"
      title="저장소"
      description="문서화 대상 소스 저장소를 등록·관리합니다 — 시스템 설정(SCM 인스턴스·문서 허브)은 설정 페이지로"
      actions={(isLoading || hasSources) && <button className="primaryBtn" onClick={onOpenWizard}><Plus size={15} />소스 추가</button>}
    />

    {isLoading && <LoadingBlock />}
    {isError && <ErrorBanner message={error?.message} onRetry={onRetry} />}

    {!isLoading && !isError && <>
      <section className="panel">
        <div className="panelHead">
          <h2>소스</h2>
          {hasSources && <label className="search"><Search size={15} /><input value={query} onChange={e => onQueryChange(e.target.value)} placeholder="소스 검색" /></label>}
        </div>
        {hasSources
          ? <SourcesTable sources={visibleSources} onOpenDetail={onOpenDetail} onVerify={onVerifySource} onTrigger={onTriggerSource} onToggleEnabled={onToggleSourceEnabled} onDelete={onDeleteSource} />
          : <EmptyState icon={Server} title="등록된 소스가 없습니다" description="GitLab 또는 GitHub 저장소를 연결해 문서 자동화를 시작하세요" actionLabel="+ 소스 추가" onAction={onOpenWizard} />}
      </section>
    </>}
  </div>;
}
