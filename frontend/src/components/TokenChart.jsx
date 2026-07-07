import {useRef, useState} from 'react';
import {fmtClock, fmtNum, nf} from '../lib/format.js';

export function TokenChart({series}) {
  const ref = useRef(null);
  const [tip, setTip] = useState(null);
  const W = 920, H = 230, M = {l: 52, r: 68, t: 12, b: 28};
  if (series.length < 2) return <div className="emptyPanel">usage 이벤트 2건부터 표시됩니다</div>;
  const pts = series.length > 420 ? series.filter((_, i) => i % Math.ceil(series.length / 420) === 0) : series;
  const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
  const max = Math.max(1, pts[pts.length - 1].in, pts[pts.length - 1].out);
  const x = t => M.l + ((t - t0) / Math.max(1, t1 - t0)) * (W - M.l - M.r);
  const y = v => H - M.b - (v / max) * (H - M.t - M.b);
  const path = key => pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p[key]).toFixed(1)}`).join('');
  const grid = [0, 0.25, 0.5, 0.75, 1].map(r => ({v: max * r, y: y(max * r)}));
  const screen = pts.map(p => ({...p, px: x(p.t)}));
  const onMove = ev => {
    const box = ref.current.getBoundingClientRect();
    const vx = ((ev.clientX - box.left) / box.width) * W;
    let best = screen[0];
    for (const p of screen) if (Math.abs(p.px - vx) < Math.abs(best.px - vx)) best = p;
    setTip({p: best, left: Math.min((best.px / W) * box.width + 12, box.width - 180)});
  };
  return (
    <div className="chartWrap" onMouseMove={onMove} onMouseLeave={() => setTip(null)} ref={ref}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {grid.map(g => <g key={g.y}><line x1={M.l} y1={g.y} x2={W - M.r} y2={g.y} /><text x={M.l - 8} y={g.y + 4}>{fmtNum(Math.round(g.v))}</text></g>)}
        <path className="line in" d={path('in')} />
        <path className="line out" d={path('out')} />
        {tip && <line className="cross" x1={tip.p.px} x2={tip.p.px} y1={M.t} y2={H - M.b} />}
        <text x={M.l} y={H - 6}>{fmtClock(t0)}</text>
        <text x={W - M.r} y={H - 6} textAnchor="end">{fmtClock(t1)}</text>
      </svg>
      {tip && <div className="tooltip" style={{left: tip.left, top: 10}}>
        <strong>{fmtClock(tip.p.t)}</strong>
        <span><i className="sw in" />입력 {nf.format(tip.p.in)}</span>
        <span><i className="sw out" />출력 {nf.format(tip.p.out)}</span>
      </div>}
    </div>
  );
}
