import {RunsTable} from './RunsTable.jsx';

// 소스 상세용 run 히스토리 — 시간순(서버가 created_at desc로 반환), source 컬럼은 문맥상 불필요해 숨김
export function SourceRunHistory({rows, onSelect}) {
  if (!rows.length) return <div className="emptyPanel">이 소스의 run 이력이 없습니다 — 지금 실행해 보세요</div>;
  return <RunsTable rows={rows} onSelect={onSelect} hideSource />;
}
