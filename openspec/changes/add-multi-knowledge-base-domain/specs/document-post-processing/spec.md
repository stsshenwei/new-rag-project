## ADDED Requirements

### Requirement: 上传后文档后处理
系统 SHALL 在文档基础解析、分块和索引成功后，触发独立的概要、关键词和建议问题生成流程。

#### Scenario: 基础入库后触发 enrichment
- **WHEN** 文档完成 chunk 持久化、Dense/keyword 索引并处于可检索状态
- **THEN** 系统 SHALL 将 `summary_status` 更新为 `pending`，随后执行概要、关键词和建议问题生成

#### Scenario: Provider 未配置
- **WHEN** 知识库未配置可用的概要模型或 enrichment 功能被关闭
- **THEN** 系统 SHALL 将状态保持为 `none` 或明确的 skipped 状态，且文档 SHALL 继续可检索

### Requirement: 概要元数据与可追溯性
系统 SHALL 保存文档概要、关键词、建议问题及生成来源信息，并绑定原文档和知识库。

#### Scenario: 概要生成成功
- **WHEN** enrichment Provider 返回有效结果
- **THEN** 系统 SHALL 保存有界概要、去重关键词、去重建议问题、模型引用、生成时间、版本和 `completed` 状态

#### Scenario: 跨知识库写入被拒绝
- **WHEN** enrichment 结果的 document 或 knowledge-base identity 与任务来源不一致
- **THEN** repository SHALL 拒绝写入并记录失败，不得污染其他知识库

### Requirement: 长文档有界摘要
系统 SHALL 对输入模型的文档内容设置长度和分段边界，禁止无界拼接全文。

#### Scenario: Parent chunks 超过模型输入限制
- **WHEN** 待摘要 parent chunks 超过配置的 token 上限
- **THEN** 系统 SHALL 分批生成局部摘要后再汇总，并保留来源 chunk ID 集合供审计

### Requirement: 失败隔离与重试
概要生成失败 SHALL NOT 将已成功解析和索引的文档标记为入库失败。

#### Scenario: LLM 调用失败
- **WHEN** enrichment 模型超时、限流、返回无效格式或不可用
- **THEN** 系统 SHALL 将 `summary_status` 标记为 `failed`、保存脱敏错误、保持文档可检索并允许有限重试

#### Scenario: 用户重试概要生成
- **WHEN** 用户对失败或过期概要发起重试
- **THEN** 系统 SHALL 创建新的版本化 enrichment 尝试，不得重复解析或重建原始文档索引

### Requirement: 概要用途限制
生成概要 SHALL 只用于知识管理导航、建议问题和可选召回增强，不得成为事实答案的唯一引用来源。

#### Scenario: 回答使用概要命中
- **WHEN** 检索通过概要或建议问题找到文档
- **THEN** 最终回答上下文和 citation SHALL 回查并引用原始 `document_chunk`
