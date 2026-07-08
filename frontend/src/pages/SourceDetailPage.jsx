import {useState} from 'react';
import {ArrowLeft, GitBranch, History, Play, ShieldCheck, Monitor} from 'lucide-react';
import {SourceEditor} from '../components/SourceEditor.jsx';
import {SourceRunHistory} from '../components/SourceRunHistory.jsx';
import {SourceSchedulesPanel} from '../components/SourceSchedulesPanel.jsx';
import {ManualProfilePanel} from '../components/ManualProfilePanel.jsx';
import {ScenarioEditor} from '../components/ScenarioEditor.jsx';
import {ArtifactSelectorPanel} from '../components/ArtifactSelectorPanel.jsx';
import {EmptyState} from '../components/EmptyState.jsx';
import {PageHeader} from '../components/PageHeader.jsx';
import {formatSchedule} from '../lib/schedule.js';
import {
  useManualProfileQuery, useSaveManualProfileMutation, usePreflightManualProfileMutation,
  useScenariosQuery, useCreateScenarioMutation, useUpdateScenarioMutation,
  useDeleteScenarioMutation, useActivateScenarioMutation, useLintScenariosMutation,
  usePreflightArtifactMutation,
} from '../hooks/queries.js';

const DETAIL_TABS = [
  {id: 'overview', label: '개요'},
  {id: 'manual', label: '매뉴얼 자동화'},
];

export function SourceDetailPage({
  source, runs, onBack, onSelectRun, onTrigger, onVerify, verifyResult,
  editForm, onEditFormChange, onSaveEdit, saveBusy, saveMessage,
  onCreateSchedule, onUpdateSchedule, onDeleteSchedule, scheduleBusy,
}) {
  const [editing, setEditing] = useState(false);
  const [detailTab, setDetailTab] = useState('overview');
  if (!source) return <EmptyState title="소스를 찾을 수 없습니다" actionLabel="목록으로" onAction={onBack} />;

  return <div>
    <PageHeader
      title={source.label}
      description={!source.enabled ? `비활성 · ${source.disabled_reason || '수동 비활성화됨'}` : `${source.kind} · ${source.project_id}`}
      actions={<>
        <button className="iconTextBtn" onClick={onBack}><ArrowLeft size={15} />목록</button>
        <button type="button" className="iconTextBtn" onClick={() => onVerify(source.id)}><ShieldCheck size={15} />검증</button>
        <button type="button" className="iconTextBtn" disabled={!source.enabled} onClick={() => onTrigger(source.id)} title={source.enabled ? undefined : source.disabled_reason}><Play size={15} />실행</button>
        <button type="button" className="primaryBtn" onClick={() => setEditing(e => !e)}>{editing ? '수정 닫기' : '수정'}</button>
      </>}
    />

    {verifyResult && <div className={verifyResult.verified ? 'verifyBox ok' : 'verifyBox bad'}>
      {verifyResult.verified ? <p><ShieldCheck size={13} /> 검증 성공 — HEAD {(verifyResult.head_sha || '').slice(0, 12)}</p> : <p>검증 실패: {verifyResult.error}</p>}
    </div>}

    <nav className="tabs">
      {DETAIL_TABS.map(({id, label}) => (
        <button key={id} className={detailTab === id ? 'active' : ''} onClick={() => setDetailTab(id)}>
          {id === 'manual' && <Monitor size={13} style={{marginRight: 4, verticalAlign: 'middle'}} />}
          {label}
        </button>
      ))}
    </nav>

    {detailTab === 'overview' && <>

    {editing && <section className="panel" style={{marginTop: 12}}>
      <SourceEditor form={editForm} onChange={onEditFormChange} onSave={onSaveEdit} onVerify={() => onVerify(source.id)} onTrigger={onTrigger} busy={saveBusy} message={saveMessage} verifyResult={null} />
    </section>}

    <div className="sourceMetaGrid">
      <section className="panel">
        <div className="panelHead"><h2>메타 정보</h2></div>
        <dl className="metaList">
          <dt>인스턴스</dt><dd>{source.instance_label || source.url || '-'}</dd>
          <dt>repo</dt><dd className="mono">{source.project_id}</dd>
          <dt>doc_dir</dt><dd className="mono">{source.doc_dir || '-'}</dd>
          <dt>스케줄</dt><dd>{source.schedules?.length ? `${source.schedules.length}개` : formatSchedule(source)}</dd>
          <dt>담당자</dt><dd>{source.owner_email || '-'}</dd>
        </dl>
      </section>

      <section className="panel branchCard">
        <div className="panelHead"><h2><GitBranch size={14} />dev 브랜치</h2></div>
        <dl className="metaList">
          <dt>브랜치명</dt><dd className="mono">{source.dev_branch || '-'}</dd>
          <dt>last sha</dt><dd className="mono">{source.last_processed_sha ? source.last_processed_sha.slice(0, 16) : '-'}</dd>
        </dl>
      </section>

      <section className="panel branchCard">
        <div className="panelHead"><h2><GitBranch size={14} />release 브랜치</h2></div>
        <dl className="metaList">
          <dt>브랜치명</dt><dd className="mono">{source.release_branch || '(default)'}</dd>
          <dt>last sha</dt><dd className="mono">{source.release_last_processed_sha ? source.release_last_processed_sha.slice(0, 16) : '-'}</dd>
        </dl>
      </section>
    </div>

    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead"><h2>자동 실행 스케줄</h2><p className="panelHint">저장소별로 여러 파이프라인 스케줄을 등록합니다</p></div>
      <SourceSchedulesPanel
        source={source}
        onCreate={onCreateSchedule}
        onUpdate={onUpdateSchedule}
        onDelete={onDeleteSchedule}
        busy={scheduleBusy}
      />
    </section>

    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead"><h2>에이전트 run 히스토리</h2></div>
      {runs.length
        ? <SourceRunHistory rows={runs} onSelect={onSelectRun} />
        : <EmptyState icon={History} title="이 소스의 run 이력이 없습니다" description="지금 실행하면 여기에 시간순으로 기록됩니다" actionLabel="이 소스로 첫 실행" onAction={() => onTrigger(source.id)} />}
    </section>
    </>}

    {detailTab === 'manual' && <ManualAutomationSection source={source} />}
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
        onPreflight={() => preflightMut.mutate({sourceId: source.id})}
        preflightResult={preflightMut.data}
        busy={saveMut.isPending || preflightMut.isPending}
      />
    </section>

    <section className="panel" style={{marginTop: 12}}>
      <div className="panelHead"><h2>시나리오 세트</h2></div>
      <ScenarioEditor
        scenarios={scenariosQ.data || []}
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
