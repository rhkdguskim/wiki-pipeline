import {useState} from 'react';
import {KeyRound} from 'lucide-react';

export function TokenSettings({onSaved}) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(localStorage.getItem('cp_token') || '');
  const save = () => {
    if (value.trim()) localStorage.setItem('cp_token', value.trim());
    else localStorage.removeItem('cp_token');
    setOpen(false);
    onSaved?.();
  };
  return <span className="tokenSettings">
    <button className="iconBtn" onClick={() => setOpen(!open)} title="Control Plane API 토큰 (CONTROL_API_TOKENS 설정 시 필요)"><KeyRound size={16} /></button>
    {open && <span className="tokenPop">
      <input type="password" value={value} onChange={e => setValue(e.target.value)} placeholder="API 토큰 (비우면 dev 무인증)" />
      <button className="primaryBtn" onClick={save}>저장</button>
    </span>}
  </span>;
}
