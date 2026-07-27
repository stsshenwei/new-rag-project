import assert from "node:assert/strict";
import test from "node:test";
import { toKnowledgeBaseCreateInput, validateKnowledgeCreationSettings } from "./knowledge-validation.ts";

const baseSettings = {
  name: " 产品资料 ",
  description: " 文档知识库 ",
  type: "document",
  activeSection: "basic",
  indexingStrategy: {
    dense_enabled: true,
    keyword_enabled: true,
    graph_enabled: false,
  },
  parser: {
    engine: "default",
    readOnly: true,
  },
  chunking: {
    strategy: "auto",
    parent_chunk_size_chars: 4096,
    child_chunk_size_chars: 384,
    child_chunk_overlap_chars: 76,
    parent_child_enabled: true,
  },
  processing: {
    question_generation_enabled: false,
    enrichment_enabled: false,
    ocr_enabled: false,
    multimodal_enabled: false,
    audio_enabled: false,
  },
};

test("blocks empty knowledge-base names without losing wizard section context", () => {
  const result = validateKnowledgeCreationSettings({ ...baseSettings, name: "   " });

  assert.deepEqual(result, { ok: false, section: "basic", message: "请输入知识库名称" });
});

test("blocks unsupported knowledge-base types", () => {
  const result = validateKnowledgeCreationSettings({ ...baseSettings, type: "faq", activeSection: "type" });

  assert.deepEqual(result, { ok: false, section: "type", message: "当前仅支持 Document 类型知识库" });
});

test("builds supported create payload while preserving requested settings", () => {
  const payload = toKnowledgeBaseCreateInput({
    ...baseSettings,
    indexingStrategy: { dense_enabled: true, keyword_enabled: false, graph_enabled: true },
    parser: { engine: "default", readOnly: true },
  });

  assert.equal(payload.name, "产品资料");
  assert.equal(payload.description, "文档知识库");
  assert.deepEqual(payload.indexing_strategy, {
    dense_enabled: true,
    keyword_enabled: false,
    graph_enabled: true,
  });
  assert.equal(payload.provider_config.parser, "default");
});
