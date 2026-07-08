import {useEffect, useMemo, useRef, useState} from 'react';
import {AlertTriangle, FileText, X} from 'lucide-react';
import mermaid from 'mermaid';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {useRunDocQuery} from '../hooks/queries.js';

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  fontFamily: 'JetBrains Mono, ui-monospace, monospace',
  flowchart: {htmlLabels: true, curve: 'basis'},
  securityLevel: 'strict',
});

let _mermaidSeq = 0;

/**
 * DocViewer — modal that renders a generated markdown doc with mermaid support.
 *
 * Props:
 *   runId, path, onClose
 */
export function DocViewer({runId, path, onClose}) {
  const {data, isLoading, isError, error} = useRunDocQuery(runId, path);
  const [view, setView] = useState('rendered'); // 'rendered' | 'raw'

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const content = data?.content || '';

  return <div className="docViewerOverlay" onClick={onClose}>
    <div className="docViewer" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={`문서 미리보기: ${path}`}>
      <header className="docViewerHead">
        <div className="docViewerPath">
          <small>DOC · {runId?.slice(0, 12) || '-'}</small>
          <strong className="mono" title={path}>{path}</strong>
        </div>
        <button type="button" className="iconBtn" onClick={onClose} aria-label="닫기"><X size={16} /></button>
      </header>
      <nav className="docViewerTabs">
        <button type="button" className={`docViewerTab ${view === 'rendered' ? 'active' : ''}`} onClick={() => setView('rendered')}>미리보기</button>
        <button type="button" className={`docViewerTab ${view === 'raw' ? 'active' : ''}`} onClick={() => setView('raw')}>원문</button>
      </nav>
      <div className={`docViewerBody ${isLoading ? 'loading' : isError ? 'error' : ''}`}>
        {isLoading && '로드 중…'}
        {isError && <div style={{display: 'grid', gap: 8, justifyItems: 'center'}}>
          <AlertTriangle size={28} />
          <span>{error?.message || '문서를 불러올 수 없습니다'}</span>
        </div>}
        {!isLoading && !isError && view === 'rendered' && <Markdown content={content} />}
        {!isLoading && !isError && view === 'raw' && <pre className="mdRaw"><code>{content}</code></pre>}
      </div>
    </div>
  </div>;
}

/**
 * Markdown renderer with mermaid diagram support.
 * - react-markdown + remark-gfm for tables/strikethrough/autolink
 * - Custom code block renderer detects ```mermaid and renders SVG via mermaid.render
 */
function Markdown({content}) {
  return <div className="mdRoot">
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
      code: CodeBlock,
    }}>
      {content}
    </ReactMarkdown>
  </div>;
}

function CodeBlock({inline, className, children, ...props}) {
  const text = String(children ?? '');
  const langMatch = /language-(\w+)/.exec(className || '');
  const lang = langMatch?.[1]?.toLowerCase();

  // mermaid block — render to SVG
  if (!inline && lang === 'mermaid') {
    return <MermaidBlock text={text} />;
  }

  // inline code or non-mermaid block
  if (inline) {
    return <code className={className} {...props}>{children}</code>;
  }
  return <pre><code className={className} {...props}>{children}</code></pre>;
}

function MermaidBlock({text}) {
  const containerRef = useRef(null);
  const [svg, setSvg] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const id = `mmd-${++_mermaidSeq}`;
    mermaid.render(id, text).then(({svg}) => {
      if (!cancelled) { setSvg(svg); setErr(null); }
    }).catch(e => {
      if (!cancelled) setErr(e?.message || '머메이드 렌더 실패');
    });
    return () => { cancelled = true; };
  }, [text]);

  if (err) return <div className="mdMermaidError" title={err}>
    <AlertTriangle size={14} /><span>머메이드 문법 오류 — 원문 탭에서 확인</span>
  </div>;
  if (!svg) return <div className="mermaid" ref={containerRef}><span className="mono" style={{color: 'var(--soft)'}}>렌더 중…</span></div>;
  return <div className="mermaid" ref={containerRef} dangerouslySetInnerHTML={{__html: svg}} />;
}
