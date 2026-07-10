import {useState} from 'react';
import {ArrowLeft, GitBranch, History, ShieldCheck, Monitor, Play, FileText, CalendarClock} from 'lucide-react';
import {SourceEditor, SOURCE_FIELD_GROUPS} from '../components/SourceEditor.jsx';
import {SourceRunHistory} from '../components/SourceRunHistory.jsx';
import {ManualProfilePanel} from '../components/ManualProfilePanel.jsx';
import {ScenarioEditor} from '../components/ScenarioEditor.jsx';
import {ArtifactSelectorPanel} from '../components/ArtifactSelectorPanel.jsx';
import {TriggerDialog} from '../components/TriggerDialog.jsx';
import {EmptyState} from '../components/EmptyState.jsx';
import {PageHeader} from '../components/PageHeader.jsx';
import {formatSchedule} from '../lib/schedule.js';
import {
  useManualProfileQuery, useSaveManualProfileMutation, usePreflightManualProfileMutation,
  useScenariosQuery, useCreateScenarioMutation, useUpdateScenarioMutation,
  useDeleteScenarioMutation, useActivateScenarioMutation, useLintScenariosMutation,
  usePreflightArtifactMutation,
} from '../hooks/queries.js';

// 저장소 상세 탭 — 설정을 관심사별로 나눠 관리.
//   overview: 메타 + 공용 저장소 연결 편집(ID/이름/종류/URL/토큰/담당자) + run 이력
//   static  : docu-automation 고유 설정 — 테마 + dev/release 브랜치 + doc_dir 만
//   manual  : manual-automation 설정 — MCP 프로파일/시나리오/아티팩트
// 저장소 연결은 공용이라 개요에 두고, 각 파이프라인 탭은 "무엇을/어떻게 만들지"만 다룬다.
// 스케줄(언제 돌릴지)은 여기서 다루지 않는다 — 별도 `스케줄러` 탭으로 분리됨.
const DETAIL_TABS = [
  {id: 'overview', label: '개요'},
  {id: 'static', label: 'docu-automation', icon: FileText},
  {id: 'manual', label: 'manual-automation', icon: Monitor},
];

export function SourceDetailPage({
  source, runs, onBack, onSelectRun, onTrigger, onVerify, verifyResult,
  editForm, onEditFormChange, onSaveEdit, saveBusy, saveMessage,
  onOpenScheduler,
}) {
  const [detailTab, setDetailTab] = useState('overview');
  const [triggerOpen, setTriggerOpen] = useState(false);
  if (!source) return <EmptyState title="소스를 찾을 수 없습니다" actionLabel="목록으로" onAction={onBack} />;

  return <div>
    <PageHeader
      title={source.label}
      description={!source.enabled ? `비활성 · ${source.disabled_reason || '수동 비활성화됨'}` : `${source.kind} · ${source.project_id}`}
      actions={<>
        <button className="iconTextBtn" onClick={onBack}><ArrowLeft size={15} />목록</button>
        <button type="button" className="iconTextBtn" onClick={() => onVerify(source.id)}><ShieldCheck size={15} />검증</button>
        <button type="button" className="iconTextBtn" disabled={!source.enabled} onClick={() => setTriggerOpen(true)} title={source.enabled ? '파이프라인 실행 wizard 열기' : source.disabled_reason}>
          <Play size={15} />실행
        </button>
      </>}
    />

    {verifyResult && <div className={verifyResult.verified ? 'verifyBox ok' : 'verifyBox bad'}>
      {verifyResult.verified ? <p><ShieldCheck size={13} /> 검증 성공 — HEAD {(verifyResult.head_sha || '').slice(0, 12)}</p> : <p>검증 실패: {verifyResult.error}</p>}
    </div>}

    <nav className="tabs">
      {DETAIL_TABS.map(({id, label, icon: Icon}) => (
        <button key={id} className={detailTab === id ? 'active' : ''} onClick={() => setDetailTab(id)}>
          {Icon && <Icon size={13} style={{marginRight: 4, verticalAlign: 'middle'}} />}
          {label}
        </button>
      ))}
    </nav>

    {detailTab === 'overview' && <>

    <div className="sourceMetaGrid">
      <section className="panel">
        <div className="panelHead"><h2>메타 정보</h2></div>
        <dl className="metaList">
          <dt>인스턴스</dt><dd>{source.instance_label || source.url || '-'}</dd>
          <dt>repo</dt><dd className="mono">{source.project_id}</dd>
          <dt>doc_dir</dt><dd className="mono">{source.doc_dir || '-'}</dd>
          <dt>스케줄</dt>
          <dd>
            {source.schedules?.length ? `${source.schedules.length}개` : formatSchedule(source)}
            {onOpenScheduler && <button type="button" className="linkBtn" style={{marginLeft: 8}} onClick={onOpenScheduler}>
              <CalendarClock size={12} />스케줄러에서 관리
            </button>}
          </dd>
          <dt>담당자</dt><dd>{source.owner_email || '-'}</dd>
        </dl>
      </section>

      <section className="panel branchCard">
        <div className="panelHead"><h2><GitBranch size={14} />dev 브랜치</h2></div>
        <dl className="metaList">
          <dt>브랜치명</dt><dd className="mono">{source.dev_branch || '-'}</dd>
          <dt>last sha</dt><dd className="mono"><LastShaValue sha={source.last_processed_sha} runs={runs} /></dd>
        </dl>
      </section>

      <section className="panel branchCard">
        <div className="panelHead"><h2><GitBranch size={14} />release 브랜치</h2></div>
        <dl className="metaList">
          <dt>브랜치명</dt><dd className="mono">{source.release_branch || '(default)'}</dd>
          <dt>last sha</dt><dd className="mono"><LastShaValue sha={source.release_last_processed_sha} runs={runs} branchRole="release" /></dd>
        </dl>
      </section>
    </div>

    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead">
        <h2>저장소 연결 (공용)</h2>
        <p className="panelHint">모든 파이프라인이 공유하는 소스 정보 — 연결·인증·담당자</p>
      </div>
      <SourceEditor
        form={editForm}
        onChange={onEditFormChange}
        onSave={onSaveEdit}
        onVerify={() => onVerify(source.id)}
        onTrigger={onTrigger}
        busy={saveBusy}
        message={saveMessage}
        verifyResult={null}
        title="저장소 연결"
        fields={SOURCE_FIELD_GROUPS.common}
      />
    </section>

    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead"><h2>에이전트 run 히스토리</h2></div>
      {runs.length
        ? <SourceRunHistory rows={runs} onSelect={onSelectRun} />
        : <EmptyState icon={History} title="이 소스의 run 이력이 없습니다" description="실행 wizard 에서 파이프라인 종류와 옵션을 정한 뒤 기록됩니다" actionLabel="이 소스로 첫 실행" onAction={() => setTriggerOpen(true)} />}
    </section>
    </>}

    {detailTab === 'static' && <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead">
        <h2><FileText size={14} />docu-automation 설정</h2>
        <p className="panelHint">이 파이프라인이 <b>어떤 테마</b>를 <b>어떤 브랜치</b>로 만들지 — 저장소 연결은 개요 탭(공용)에서 관리</p>
      </div>
      <SourceEditor
        form={editForm}
        onChange={onEditFormChange}
        onSave={onSaveEdit}
        onVerify={() => onVerify(source.id)}
        onTrigger={onTrigger}
        busy={saveBusy}
        message={saveMessage}
        verifyResult={null}
        title="정적 문서 자동화"
        fields={SOURCE_FIELD_GROUPS.docu}
        showTrigger={false}
      />
    </section>}

    {detailTab === 'manual' && <ManualAutomationSection source={source} />}

    <TriggerDialog
      open={triggerOpen}
      source={source}
      onClose={() => setTriggerOpen(false)}
      onSubmit={async (sourceId, opts) => {
        await onTrigger(sourceId, opts);
        setTriggerOpen(false);
      }}
    />
  </div>;
}

function ManualAutomationSection({source, artifactPreflight, setArtifactPreflight, artifactBusy, setArtifactBusy}) {
  const profileQ = useManualProfileQuery(source.id);
  const saveMut = useSaveManualProfileMutation();
  const preflightMut = usePreflightManualProfileMutation();
  const scenariosQ = useScenariosQuery(source.id);
  const createScenarioMut = useCreateScenarioMutation();
  const updateScenarioMut = useUpdateScenarioMutation();
  const deleteScenarioMut = useDeleteScenarioMutation();
  const activateScenarioMut = useActivateScenarioMutation();
  const lintMut = useLintScenariosMutation();
  const artifactPreflightMut = usePreflightArtifactMutation();

  return <>
    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead">
        <h2><Monitor size={14} />매뉴얼 파이프라인 프로파일</h2>
        <p className="panelHint">MCP endpoint · tool allowlist · artifact selector · coverage threshold</p>
      </div>
      <ManualProfilePanel
        sourceId={source.id}
        profile={profileQ.data}
        onSave={(payload) => saveMut.mutate({sourceId: source.id, payload})}
        onPreflight={() => preflightMut.mutate(source.id)}
        preflightResult={preflightMut.data}
        busy={saveMut.isPending || preflightMut.isPending}
      />
    </section>

    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead"><h2>시나리오 세트</h2></div>
      <ScenarioEditor
        scenarios={scenariosQ.data?.scenarios || []}
        onCreate={(payload) => createScenarioMut.mutate({sourceId: source.id, payload})}
        onUpdate={(setId, payload) => updateScenarioMut.mutate({sourceId: source.id, scenarioId: setId, payload})}
        onActivate={(setId) => activateScenarioMut.mutate({sourceId: source.id, scenarioId: setId})}
        onDelete={(setId) => deleteScenarioMut.mutate({sourceId: source.id, scenarioId: setId})}
        onLint={(payload) => lintMut.mutate({sourceId: source.id, payload})}
        lintResult={lintMut.data}
        busy={createScenarioMut.isPending || updateScenarioMut.isPending}
      />
    </section>

    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead"><h2>아티팩트 선택기</h2></div>
      <ArtifactSelectorPanel
        preflightResult={artifactPreflightMut.data}
        onPreflight={(payload) => artifactPreflightMut.mutate({sourceId: source.id, payload})}
        busy={artifactPreflightMut.isPending}
      />
    </section>
  </>;
}

// last sha 표시 헬퍼 — SHA 가 비어 있을 때 그냥 "-" 로 두면 "왜 비었는지"를 알 수 없다.
// 성공(done) run 이 있는데도 SHA 가 없으면 백엔드가 idempotent-sha 포인터를 전진시키지
// 못한 상태(전진 실패 가능)임을 힌트로 알려주고, run 자체가 없으면 "실행 없음"으로 구분한다.
function LastShaValue({sha, runs, branchRole = 'dev'}) {
  if (sha) return <span title={sha}>{sha.slice(0, 16)}</span>;
  const hasSuccessfulRun = Array.isArray(runs) &&
    runs.some(r => (r.branch_role || 'dev') === branchRole && r.status === 'done');
  if (!hasSuccessfulRun) {
    return <span className="muted" title="아직 이 브랜치에서 성공한 run 이 없어 전진한 SHA 가 없습니다">실행 없음</span>;
  }
  return <span
    className="lastShaMissing"
    title="성공한 run 은 있지만 처리 SHA 포인터가 전진하지 않았습니다. 백엔드 배포 버전 또는 완료 보고의 last_processed_sha 전파를 확인하세요."
  >미전진</span>;
}
