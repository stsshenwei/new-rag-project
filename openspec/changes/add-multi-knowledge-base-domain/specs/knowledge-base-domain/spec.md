## ADDED Requirements

### Requirement: 工作空间与知识库持久化
系统 SHALL 将工作空间和知识库作为一等实体持久化，并且每个知识库 SHALL 且只能属于一个工作空间。

#### Scenario: 创建文档型知识库
- **WHEN** 客户端在活动工作空间中使用有效名称创建知识库
- **THEN** 系统 SHALL 保存唯一知识库 ID、工作空间 ID、`document` 类型、描述、活动状态、配置和时间戳

#### Scenario: 拒绝不支持的知识库类型
- **WHEN** 客户端在本阶段请求 FAQ、Wiki 或未知知识库类型
- **THEN** 系统 SHALL 返回类型化校验错误，并且 SHALL NOT 创建不完整记录

### Requirement: 兼容默认实体
系统 SHALL 为现有部署和客户端维护一个确定性的默认工作空间和默认文档型知识库。

#### Scenario: 首次启动创建默认实体
- **WHEN** clean-rebuild 已完成且应用首次启动，配置的默认工作空间或知识库不存在
- **THEN** 系统 SHALL 使用稳定配置 ID 幂等创建它们

#### Scenario: 重复启动复用默认实体
- **WHEN** 默认实体已经存在时应用再次启动
- **THEN** 系统 SHALL 复用原实体，不得创建重复记录或修改其 ID

### Requirement: 知识库生命周期 API
系统 SHALL 通过轻量 HTTP handler 和知识库 service/repository 边界提供创建、列表、详情、更新和归档操作。

#### Scenario: 查询活动知识库
- **WHEN** 客户端查询工作空间知识库且未要求包含归档项
- **THEN** 系统 SHALL 返回活动知识库及文档、chunk、处理中和失败聚合数量

#### Scenario: 更新知识库元数据
- **WHEN** 客户端修改活动知识库的名称、描述或受支持配置
- **THEN** 系统 SHALL 校验并保存修改，不得重写文档或向量

#### Scenario: 归档知识库
- **WHEN** 客户端通过第一版生命周期 API 删除活动知识库
- **THEN** 系统 SHALL 将其标记为归档、从默认列表排除并禁止新增上传和检索，但 SHALL NOT 物理清空内容

### Requirement: 知识库配置契约
系统 SHALL 为每个知识库保存经过校验的索引策略和 Provider 引用配置。

#### Scenario: 使用默认配置创建
- **WHEN** 客户端创建知识库且没有提供索引或 Provider 配置
- **THEN** 系统 SHALL 使用当前有效的 Dense、keyword、graph、parser、embedding、reranker 和 vector-store 默认配置

#### Scenario: Provider 覆盖值尚不受支持
- **WHEN** 知识库引用了当前运行时工厂无法激活的 Provider 覆盖配置
- **THEN** 系统 SHALL 分别保留 requested/effective 配置，并将覆盖项报告为未生效，而不是静默应用

### Requirement: 知识库聚合状态
系统 SHALL 根据权威文档、chunk、解析任务和索引状态计算知识库摘要。

#### Scenario: 部分文档处理失败
- **WHEN** 一部分文档已索引而其他文档或解析任务失败
- **THEN** 知识库详情和目录摘要 SHALL 同时报告成功数量与失败数量，不得把全部内容标记为不可用
