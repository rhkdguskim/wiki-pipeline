import {useEffect, useMemo, useState} from 'react';
import {CalendarClock, ChevronRight, Pencil, Plus, Search, Server} from 'lucide-react';
import {PageHeader} from '../components/PageHeader.jsx';
import {ScheduleDialog} from '../components/ScheduleDialog.jsx';
import {EmptyState} from '../components/EmptyState.jsx';
import {formatSchedule} from '../lib/schedule.js';

/**
 * SchedulerPage — 자동 실행 스케줄 관리 (마스터-디테일 + 모달).
 *
 *   ┌ 저장소 트리 ─┐┌ 선택된 저장소 스케줄 상세 ──────────┐
 *   │ ▸ repo A (2) ││  [스케줄 추가]                       │
 *   │ ▸ repo B (0) ││  · 정적 · 월~금 20:00  [편집]        │
 *   └─────────────┘└──────────────────────────────────────┘
 *
 * 파이프라인 설정(소스 자체)은 `저장소` 탭에 두고, 여기서는 "언제 돌릴지"만.
 * 추가/편집은 ScheduleDialog(모달)로 처리해 목록 화면을 깔끔하게 유지한다.
 *
 * onCreate/onUpdate/onDelete 는 sourceId 를 첫 인자로 받는다(App 에서 주입).
 */
export function SchedulerPage({
  sources, onCreate, onUpdate, onDelete, scheduleBusy,
  isLoading, isError, error, onRetry,
}) {
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  // dialog: null(닫힘) | {schedule: null} (추가) | {schedule: row} (편집)
  const [dialog, setDialog] = useState(null);

  const enabledSources = useMemo(
    () => (sources || []).filter(s => s.enabled !== false),
    [sources],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return enabledSources;
    return enabledSources.filter(s =>
      (s.label || '').toLowerCase().includes(q) ||
      (s.project_id || '').toLowerCase().includes(q),
    );
  }, [enabledSources, query]);

  // 첫 진입/필터 변경 시 유효한 저장소를 자동 선택.
  useEffect(() => {
    if (selectedId && filtered.some(s => s.id === selectedId)) return;
    setSelectedId(filtered[0]?.id ?? null);
  }, [filtered, selectedId]);

  const selected = enabledSources.find(s => s.id === selectedId) || null;

  const totalSchedules = useMemo(
    () => enabledSources.reduce((n, s) => n + (s.schedules?.length || 0), 0),
    [enabledSources],
  );

  if (isLoading) return <div className="panel"><div className="emptyPanel">스케줄 불러오는 중…</div></div>;
  if (isError) return <div className="panel"><div className="emptyPanel errText">
    스케줄 조회 실패: {error?.message}
    {onRetry && <button type="button" className="iconTextBtn" style={{marginLeft: 8}} onClick={onRetry}>다시 시도</button>}
  </div></div>;

  // 모달 저장 — 추가/편집 분기. 성공 시 닫는다(mutation 실패는 toast 로 표면화됨).
  const handleSave = async (payload) => {
    if (!selected) return;
    if (dialog?.schedule) await onUpdate(selected.id, dialog.schedule.id, payload);
    else await onCreate(selected.id, payload);
    setDialog(null);
  };
  const handleDelete = async () => {
    if (!selected || !dialog?.schedule) return;
    if (!confirm('이 스케줄을 삭제할까요?')) return;
    await onDelete(selected.id, dialog.schedule.id);
    setDialog(null);
  };

  return <div>
    <PageHeader
      eyebrow="SCHEDULER"
      title="스케줄러"
      description="저장소를 골라 파이프라인 자동 실행 스케줄을 관리합니다"
      actions={<span className="pill small">{enabledSources.length}개 저장소 · 스케줄 {totalSchedules}개</span>}
    />

    {!enabledSources.length ? (
      <EmptyState
        icon={Server}
        title="활성 저장소가 없습니다"
        description="스케줄을 걸려면 먼저 저장소 탭에서 파이프라인 소스를 등록·활성화하세요"
      />
    ) : (
      <div className="schedulerLayout">
        {/* 좌측: 저장소 트리 */}
        <aside className="schedulerTree" aria-label="저장소 목록">
          <label className="searchField schedulerTreeSearch">
            <Search size={14} />
            <input
              type="search"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="저장소 검색"
              aria-label="저장소 검색"
            />
          </label>
          <div className="schedulerTreeList" role="tree">
            {filtered.length ? filtered.map(s => {
              const count = s.schedules?.length || 0;
              const active = s.id === selectedId;
              return <button
                key={s.id}
                type="button"
                role="treeitem"
                aria-selected={active}
                className={active ? 'schedulerTreeNode active' : 'schedulerTreeNode'}
                onClick={() => setSelectedId(s.id)}
              >
                <ChevronRight size={14} className="schedulerTreeCaret" />
                <span className="schedulerTreeLabel">
                  <strong>{s.label}</strong>
                  <small className="mono">{s.project_id}</small>
                </span>
                <span className={`pill small ${count ? 'done' : ''}`}>{count}</span>
              </button>;
            }) : <div className="emptyPanel">검색 결과 없음</div>}
          </div>
        </aside>

        {/* 우측: 선택된 저장소 스케줄 상세 */}
        <section className="schedulerDetail">
          {selected ? <ScheduleDetail
            source={selected}
            onAdd={() => setDialog({schedule: null})}
            onEdit={(row) => setDialog({schedule: row})}
          /> : <EmptyState icon={CalendarClock} title="저장소를 선택하세요" description="왼쪽 트리에서 저장소를 고르면 스케줄을 관리할 수 있습니다" />}
        </section>
      </div>
    )}

    <ScheduleDialog
      open={!!dialog}
      source={selected}
      schedule={dialog?.schedule || null}
      onSave={handleSave}
      onDelete={handleDelete}
      onClose={() => setDialog(null)}
      busy={scheduleBusy}
    />
  </div>;
}

// 선택된 저장소의 스케줄 목록 + 추가 버튼.
function ScheduleDetail({source, onAdd, onEdit}) {
  const schedules = source.schedules || [];
  return <div className="panel">
    <div className="panelHead schedulerDetailHead">
      <div>
        <h2>{source.label}</h2>
        <p className="panelHint mono">{source.project_id}</p>
      </div>
      <button type="button" className="primaryBtn" onClick={onAdd}><Plus size={15} />스케줄 추가</button>
    </div>

    {schedules.length ? (
      <ul className="scheduleList">
        {schedules.map(row => <li key={row.id} className="scheduleRow">
          <span className={`pill small ${row.pipeline_id === 'manual' ? 'warn' : 'done'}`}>
            {row.pipeline_id === 'manual' ? '매뉴얼' : '정적'}
          </span>
          <div className="scheduleRowMain">
            <strong>{row.label || (row.pipeline_id === 'manual' ? '매뉴얼 자동화' : '정적 문서 자동화')}</strong>
            <small className="muted">
              <CalendarClock size={12} /> {formatSchedule(row)}
              {row.pipeline_id !== 'manual' && ` · ${row.mode}/${row.branch_role}`}
            </small>
          </div>
          {row.enabled === false && <span className="pill small stalled">비활성</span>}
          <button type="button" className="iconTextBtn" onClick={() => onEdit(row)}><Pencil size={13} />편집</button>
        </li>)}
      </ul>
    ) : (
      <EmptyState
        icon={CalendarClock}
        title="등록된 스케줄이 없습니다"
        description="이 저장소의 파이프라인을 자동 실행하려면 스케줄을 추가하세요"
        actionLabel="스케줄 추가"
        onAction={onAdd}
      />
    )}
  </div>;
}
