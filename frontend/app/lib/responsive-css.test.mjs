import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(new URL("../globals.css", import.meta.url), "utf8");
const chatPage = readFileSync(new URL("../chat/page.tsx", import.meta.url), "utf8");
const knowledgeDocumentPage = readFileSync(new URL("../knowledge/document/page.tsx", import.meta.url), "utf8");

test("processing preview layout has bounded cards and mobile single-column rules", () => {
  assert.match(css, /\.preview-diagnostics\s*{/);
  assert.match(css, /\.preview-chunk-list\s*{/);
  assert.match(css, /\.preview-chunk-card\s*{/);
  assert.match(css, /overflow-wrap:\s*anywhere/);

  const mobileBlock = css.match(/@media \(max-width: 760px\) \{[\s\S]*?\n\}/)?.[0] || "";
  assert.match(mobileBlock, /preview-diagnostics/);
  assert.match(mobileBlock, /preview-chunk-list/);
  assert.match(mobileBlock, /grid-template-columns:\s*1fr/);
});

test("chat home composer exposes enterprise controls without model selector", () => {
  assert.match(chatPage, /Hi，我是 Bee，让你的知识触手可及/);
  assert.match(chatPage, /你可以这样问我/);
  assert.match(chatPage, /快速问答/);
  assert.match(chatPage, /智能推理/);
  assert.match(chatPage, /上传文档/);
  assert.match(chatPage, /知识库：/);
  assert.doesNotMatch(chatPage, /模型/);
  assert.match(css, /\.suggested-question-list/);
  assert.match(css, /\.composer-mode-select/);
  assert.match(css, /\.composer-icon-button/);
  assert.match(css, /\.composer-attachments/);
});

test("knowledge document detail page exposes preview and chunk views", () => {
  assert.match(knowledgeDocumentPage, /文档详情/);
  assert.match(knowledgeDocumentPage, /基本信息/);
  assert.match(knowledgeDocumentPage, /摘要/);
  assert.match(knowledgeDocumentPage, /文件内容/);
  assert.match(knowledgeDocumentPage, />预览</);
  assert.match(knowledgeDocumentPage, />分块</);
  assert.match(css, /\.knowledge-document-detail-page/);
  assert.match(css, /\.document-detail-tabs/);
  assert.match(css, /\.document-detail-chunks/);
});
