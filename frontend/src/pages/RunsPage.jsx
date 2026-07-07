import {History} from 'lucide-react';
import {RunsTable} from '../components/RunsTable.jsx';
import {EmptyState} from '../components/EmptyState.jsx';
import {PageHeader} from '../components/PageHeader.jsx';
import {LoadingBlock, ErrorBanner} from '../components/QueryState.jsx';

export function RunsPage({rows, onSelect, onTrigger, sources, isLoading, isError, error, onRetry}) {
  return <div>
    <PageHeader title="실행 이력" description="전체 소스의 run 이력을 시간순으로 확인합니다" />
    {isLoading && <LoadingBlock />}
    {isError && <ErrorBanner message={error?.message} onRetry={onRetry} />}
    {!isLoading && !isError && <section className="panel">
      {rows.length
        ? <RunsTable rows={rows} onSelect={onSelect} onTrigger={onTrigger} sources={sources} />
        : <EmptyState icon={History} title="run 이력이 없습니다" description="저장소에서 소스를 실행하면 이곳에 기록됩니다" />}
    </section>}
  </div>;
}
