import {CostsPanel} from '../components/CostsPanel.jsx';
import {PageHeader} from '../components/PageHeader.jsx';
import {LoadingBlock, ErrorBanner} from '../components/QueryState.jsx';

export function CostsPage({costs, overview, isLoading, isError, error, onRetry}) {
  return <div>
    <PageHeader title="비용" description="소스별 토큰 사용량과 누적 비용 지표를 확인합니다" />
    {isLoading && <LoadingBlock />}
    {isError && <ErrorBanner message={error?.message} onRetry={onRetry} />}
    {!isLoading && !isError && <section className="panel">
      <CostsPanel costs={costs} overview={overview} />
    </section>}
  </div>;
}
