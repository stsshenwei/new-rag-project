"use client";

type DocumentViewerProps = {
  open: boolean;
  source: string;
  loading: boolean;
  error: string;
  mode: "text" | "pdf";
  content: string;
  fileUrl: string;
  onClose: () => void;
};

export function DocumentViewer({ open, source, loading, error, mode, content, fileUrl, onClose }: DocumentViewerProps) {
  if (!open) return null;

  return (
    <section className="doc-viewer-mask" onClick={onClose}>
      <article className="doc-viewer" onClick={(event) => event.stopPropagation()}>
        <header className="doc-viewer-header">
          <div className="doc-viewer-title">{source || "文档内容"}</div>
          <button type="button" className="doc-close" onClick={onClose}>
            关闭
          </button>
        </header>
        <div className="doc-viewer-body">
          {loading ? "加载中..." : null}
          {!loading && error ? `加载失败: ${error}` : null}
          {!loading && !error && mode === "text" ? content : null}
          {!loading && !error && mode === "pdf" ? <iframe title={source || "pdf"} className="doc-pdf-frame" src={fileUrl} /> : null}
        </div>
      </article>
    </section>
  );
}
