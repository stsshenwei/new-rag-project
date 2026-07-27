import type { KnowledgeCreationWizardSettings } from "./types";

export type KnowledgeCreationValidation =
  | { ok: true }
  | { ok: false; section: KnowledgeCreationWizardSettings["activeSection"]; message: string };

export function validateKnowledgeCreationSettings(settings: KnowledgeCreationWizardSettings): KnowledgeCreationValidation {
  if (!settings.name.trim()) {
    return { ok: false, section: "basic", message: "请输入知识库名称" };
  }
  if (settings.type !== "document") {
    return { ok: false, section: "type", message: "当前仅支持 Document 类型知识库" };
  }
  return { ok: true };
}

export function toKnowledgeBaseCreateInput(settings: KnowledgeCreationWizardSettings) {
  return {
    name: settings.name.trim(),
    description: settings.description.trim(),
    indexing_strategy: {
      dense_enabled: settings.indexingStrategy.dense_enabled,
      keyword_enabled: settings.indexingStrategy.keyword_enabled,
      graph_enabled: settings.indexingStrategy.graph_enabled,
    },
    provider_config: {
      parser: settings.parser.engine,
      chunk_strategy: settings.chunking.strategy || "auto",
      parent_chunk_size_chars: settings.chunking.parent_chunk_size_chars,
      child_chunk_size_chars: settings.chunking.child_chunk_size_chars,
      child_chunk_overlap_chars: settings.chunking.child_chunk_overlap_chars,
      parent_child_enabled: Boolean(settings.chunking.parent_child_enabled),
      vector_store: "default",
      embedding: "default",
      enrichment: "default",
    },
  };
}
