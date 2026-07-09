// TriggerButton — Play 버튼 + 모달 state + TriggerDialog 를 한 묶음.
//
// 어디서든 <TriggerButton source={s} onTrigger={onTrigger} /> 로 쓸 수 있다.
// - table 셀 / 헤더 / wizard 등 크기 옵션 (size: sm | md)
// - busy 상태는 외부에서 주입 (mutation isPending)
// - 사용자가 모달에서 실행 버튼을 누르면 onTrigger(sourceId, opts) 호출
//   매뉴얼은 opts.manualProfilePayload 가 같이 오며, 호출자가 profile 저장 → trigger 순서로 처리해야 한다.

import {useState} from 'react';
import {Play} from 'lucide-react';
import {TriggerDialog} from './TriggerDialog.jsx';

export function TriggerButton({
  source,
  onTrigger,
  busy = false,
  disabled = false,
  size = 'md',
  label,
  title,
}) {
  const [open, setOpen] = useState(false);
  if (!source?.id) {
    // id 없는 임시 form 상태에선 노출하지 않는다.
    return null;
  }
  const btnCls = `iconTextBtn ${size === 'sm' ? 'compact' : ''}`;
  const disabledTitle = disabled
    ? (source.disabled_reason || source.label ? `${source.label} 비활성` : '비활성')
    : null;
  const openDialog = () => {
    if (disabled || busy) return;
    setOpen(true);
  };
  return <>
    <button
      type="button"
      className={btnCls}
      onClick={openDialog}
      disabled={disabled || busy}
      title={title || disabledTitle || `${source.label || source.id} 실행`}
    >
      <Play size={size === 'sm' ? 13 : 15} />
      {label || (size === 'sm' ? '실행' : '실행')}
    </button>
    <TriggerDialog
      open={open}
      source={source}
      busy={busy}
      onClose={() => setOpen(false)}
      onSubmit={async (sourceId, opts) => {
        try {
          await onTrigger?.(sourceId, opts);
          setOpen(false);
        } catch (e) {
          // App.jsx 의 doTriggerRun 이 toast 로 에러를 띄우므로 여기서 다시 던지지 않고
          // 모달은 닫지 않는다 (사용자가 같은 옵션으로 재시도 가능).
          // 외부에서 mutation 에러가 발생했을 때 busy 가 풀리지 않는 경우를 대비해
          // 컴포넌트는 unmount 되지 않는다.
          throw e;
        }
      }}
    />
  </>;
}
