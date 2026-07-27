import type {
  ChatAttachment,
  DocumentFilters,
  DocumentItem,
  DocumentProcessingTrace,
  DocumentProcessingPreview,
  KnowledgeBase,
  ParserEngineInfo,
  ParserEnginesResponse,
  UploadBatch,
  UploadBatchSettings,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export async function readJson<T>(res: Response): Promise<T & { detail?: string }> {
  const data = (await res.json()) as T & { detail?: string };
  if (!res.ok) {
    throw new Error(data.detail || `请求失败: ${res.status}`);
  }
  return data;
}

export async function listKnowledgeBases(includeArchived = false): Promise<KnowledgeBase[]> {
  const data = await readJson<{ items?: KnowledgeBase[] }>(
    await fetch(`${API_BASE}/knowledge-bases?include_archived=${includeArchived}`),
  );
  return data.items || [];
}

export async function listParserEngines(): Promise<ParserEngineInfo[]> {
  const data = await readJson<ParserEnginesResponse>(await fetch(`${API_BASE}/parser-engines`));
  return data.items || [];
}

export async function uploadChatAttachment(file: File): Promise<ChatAttachment> {
  const form = new FormData();
  form.append("file", file);
  return readJson<ChatAttachment>(
    await fetch(`${API_BASE}/chat/attachments`, {
      method: "POST",
      body: form,
    }),
  );
}

export async function previewDocument(source: string, knowledgeBaseId?: string): Promise<DocumentProcessingPreview> {
  return readJson<DocumentProcessingPreview>(await fetch(`${API_BASE}/documents/parse`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, knowledge_base_id: knowledgeBaseId || null }),
  }));
}

export async function createKnowledgeBase(input: {
  name: string;
  description?: string;
  indexing_strategy?: Record<string, unknown>;
  provider_config?: Record<string, unknown>;
}): Promise<KnowledgeBase> {
  return readJson<KnowledgeBase>(
    await fetch(`${API_BASE}/knowledge-bases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...input, type: "document" }),
    }),
  );
}

export async function updateKnowledgeBase(
  knowledgeBaseId: string,
  input: { name?: string; description?: string },
): Promise<KnowledgeBase> {
  return readJson<KnowledgeBase>(
    await fetch(`${API_BASE}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function archiveKnowledgeBase(knowledgeBaseId: string): Promise<KnowledgeBase> {
  return readJson<KnowledgeBase>(
    await fetch(`${API_BASE}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}`, { method: "DELETE" }),
  );
}

export async function listKnowledgeBaseDocuments(
  knowledgeBaseId: string,
  filters?: Partial<DocumentFilters>,
): Promise<DocumentItem[]> {
  const params = new URLSearchParams({ knowledge_base_id: knowledgeBaseId });
  if (filters) {
    for (const [key, value] of Object.entries(filters)) {
      if (value) params.set(key, value);
    }
  }
  const data = await readJson<{ items?: DocumentItem[] }>(
    await fetch(`${API_BASE}/documents?${params.toString()}`),
  );
  return data.items || [];
}

export async function retryDocumentEnrichment(documentId: string, knowledgeBaseId: string): Promise<DocumentItem> {
  return readJson<DocumentItem>(
    await fetch(
      `${API_BASE}/documents/${encodeURIComponent(documentId)}/enrichment/retry?knowledge_base_id=${encodeURIComponent(knowledgeBaseId)}`,
      { method: "POST" },
    ),
  );
}

export async function getDocumentProcessingTrace(documentId: string, knowledgeBaseId: string): Promise<DocumentProcessingTrace> {
  return readJson<DocumentProcessingTrace>(
    await fetch(
      `${API_BASE}/documents/${encodeURIComponent(documentId)}/processing-trace?knowledge_base_id=${encodeURIComponent(knowledgeBaseId)}`,
    ),
  );
}

export async function createUploadBatch(knowledgeBaseId: string, settings: UploadBatchSettings): Promise<UploadBatch> {
  return readJson<UploadBatch>(
    await fetch(`${API_BASE}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/upload-batches`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    }),
  );
}

export async function uploadBatchFile(
  knowledgeBaseId: string,
  batchId: string,
  file: File,
  relativePath: string,
): Promise<UploadBatch> {
  const form = new FormData();
  form.append("file", file);
  form.append("relative_path", relativePath);
  return readJson<UploadBatch>(
    await fetch(`${API_BASE}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/upload-batches/${encodeURIComponent(batchId)}/files`, {
      method: "POST",
      body: form,
    }),
  );
}

export async function confirmUploadBatch(knowledgeBaseId: string, batchId: string): Promise<UploadBatch> {
  return readJson<UploadBatch>(
    await fetch(`${API_BASE}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/upload-batches/${encodeURIComponent(batchId)}/confirm`, {
      method: "POST",
    }),
  );
}

export async function getUploadBatch(knowledgeBaseId: string, batchId: string): Promise<UploadBatch> {
  return readJson<UploadBatch>(
    await fetch(`${API_BASE}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/upload-batches/${encodeURIComponent(batchId)}`),
  );
}

export async function updateUploadBatchSettings(
  knowledgeBaseId: string,
  batchId: string,
  settings: UploadBatchSettings,
): Promise<UploadBatch> {
  return readJson<UploadBatch>(
    await fetch(`${API_BASE}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/upload-batches/${encodeURIComponent(batchId)}/settings`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    }),
  );
}

export async function cancelUploadBatch(knowledgeBaseId: string, batchId: string): Promise<UploadBatch> {
  return readJson<UploadBatch>(
    await fetch(`${API_BASE}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/upload-batches/${encodeURIComponent(batchId)}/cancel`, {
      method: "POST",
    }),
  );
}

export async function retryUploadBatchFile(knowledgeBaseId: string, batchId: string, fileId: string): Promise<UploadBatch> {
  return readJson<UploadBatch>(
    await fetch(
      `${API_BASE}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/upload-batches/${encodeURIComponent(batchId)}/files/${encodeURIComponent(fileId)}/retry`,
      { method: "POST" },
    ),
  );
}
