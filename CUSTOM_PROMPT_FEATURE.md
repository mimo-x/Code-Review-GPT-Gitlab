# 项目级 Webhook 事件自定义 Prompt 功能

## 📋 功能概述

每个项目现在可以为不同的 webhook 事件类型配置不同的代码审查提示词（prompt），让 AI 更符合项目特点进行审查。

## ✨ 主要特性

### 1. 项目级配置
- 每个项目可以独立配置自己的审查提示词
- 不同的 webhook 事件类型可以使用不同的提示词
- 未配置时自动使用系统默认提示词

### 2. 变量占位符支持
自定义 prompt 中可以使用以下占位符，系统会自动替换为实际值：

| 占位符 | 说明 | 示例值 |
|--------|------|--------|
| `{project_name}` | 项目名称 | My Awesome Project |
| `{project_id}` | 项目ID | 12345 |
| `{author}` | MR 作者 | John Doe |
| `{title}` | MR 标题 | Fix critical bug |
| `{description}` | MR 描述 | This MR fixes... |
| `{source_branch}` | 源分支 | feature/fix-bug |
| `{target_branch}` | 目标分支 | main |
| `{mr_iid}` | MR 内部ID | 42 |
| `{file_count}` | 文件变更数 | 5 |
| `{changes_count}` | 代码行变更数 | 123 |

### 3. 自动创建空配置
- 当项目启用某个 webhook 事件时，系统自动创建一条空的 prompt 配置记录
- 用户可以随时开启自定义 prompt 并编辑内容

## 🗄️ 数据库设计

### 新增表：`project_webhook_event_prompts`

```sql
CREATE TABLE project_webhook_event_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    event_rule_id INTEGER NOT NULL,
    custom_prompt TEXT DEFAULT '',
    use_custom BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (event_rule_id) REFERENCES webhook_event_rules(id) ON DELETE CASCADE,
    UNIQUE (project_id, event_rule_id)
);
```

## 🔌 API 接口

### 1. 获取项目的 Webhook 事件 Prompt 配置

**接口**: `GET /api/webhook/projects/{project_id}/webhook-event-prompts/`

**响应示例**:
```json
{
  "status": "success",
  "prompts": [
    {
      "id": 1,
      "project": 1,
      "event_rule": 1,
      "event_rule_name": "MR 创建",
      "event_rule_type": "mr_open",
      "event_rule_description": "当新的 Merge Request 被创建时触发代码审查",
      "custom_prompt": "请详细审查项目 {project_name} 的 MR...",
      "use_custom": true,
      "created_at": "2025-01-10T10:00:00+08:00",
      "updated_at": "2025-01-10T10:30:00+08:00"
    }
  ]
}
```

### 2. 更新项目的 Webhook 事件 Prompt 配置

**接口**: `POST /api/webhook/projects/{project_id}/webhook-event-prompts/update/`

**请求体**:
```json
{
  "event_rule_id": 1,
  "custom_prompt": "请详细审查项目 {project_name} 的 MR...",
  "use_custom": true
}
```

**响应示例**:
```json
{
  "status": "success",
  "message": "Prompt 配置已更新",
  "prompt": {
    "id": 1,
    "event_rule": 1,
    "event_rule_name": "MR 创建",
    "custom_prompt": "请详细审查项目 {project_name} 的 MR...",
    "use_custom": true
  }
}
```

## 🎨 前端界面

### 1. 新增 Tab：审查提示词

在项目详情页面（ProjectDetail.vue）新增了"审查提示词"标签页，位于 "Webhook事件" 和 "通知设置" 之间。

### 2. 界面功能

#### 配置卡片
- 每个启用的 webhook 事件显示一个配置卡片
- 卡片头部显示事件名称、类型和描述
- 右上角有开关，控制是否使用自定义 prompt

#### Prompt 编辑器
- 当开启自定义 prompt 时显示
- 支持 Markdown 格式
- 最小高度 240px，可调整大小
- Placeholder 中包含示例和占位符说明
- 底部显示所有支持的占位符列表
- 实时保存按钮

#### 提示信息
- 顶部有功能说明和使用提示
- 显示支持的占位符和使用场景
- 未配置时提示用户先启用 webhook 事件

## ⚙️ 业务逻辑改造

### 1. Webhook 处理流程

```python
# 1. 接收 webhook 事件
gitlab_webhook(request)
  ↓
# 2. 统一事件处理
handle_webhook_event(payload, webhook_log, project_id)
  ↓
# 3. 匹配事件规则
matched_rule = WebhookEventRule.matches_payload(payload)
  ↓
# 4. 启动 MR 审查（传递 matched_rule）
_start_merge_request_review(..., matched_rule)
  ↓
# 5. 审查线程处理
process_merge_request_review(..., matched_rule)
  ↓
# 6. 查询自定义 prompt
prompt_config = ProjectWebhookEventPrompt.objects.filter(
    project__project_id=project_id,
    event_rule=matched_rule,
    use_custom=True
).first()
  ↓
# 7. 渲染 prompt（替换变量）
if prompt_config and prompt_config.custom_prompt:
    custom_prompt = prompt_config.render_prompt(mr_info)
  ↓
# 8. 调用 LLM 审查
llm_service.review_code(..., custom_prompt=custom_prompt)
```

### 2. Prompt 渲染逻辑

`ProjectWebhookEventPrompt.render_prompt(context)` 方法：

```python
def render_prompt(self, context: dict) -> str:
    """渲染 prompt 模板，替换占位符变量"""
    if not self.custom_prompt:
        return ''

    prompt = self.custom_prompt

    replacements = {
        '{project_name}': str(context.get('project_name', '')),
        '{author}': str(context.get('author', '')),
        # ... 其他占位符
    }

    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)

    return prompt
```

## 📝 使用示例

### 示例 1: 安全审查重点

```markdown
# {project_name} 安全审查

请对 MR #{mr_iid} 进行安全性审查。

**作者**: {author}
**标题**: {title}
**分支**: {source_branch} → {target_branch}

## 审查重点

1. **SQL 注入风险**
   - 检查所有数据库查询是否使用参数化查询
   - 验证用户输入是否经过严格的过滤和转义

2. **XSS 攻击防护**
   - 检查所有用户输入在输出时是否经过 HTML 转义
   - 验证 Content-Security-Policy 配置

3. **认证授权**
   - 检查接口权限验证是否完整
   - 验证敏感操作是否有二次确认

4. **敏感信息泄露**
   - 检查是否有硬编码的密钥、密码
   - 验证错误信息是否包含敏感信息

请为每个发现的问题提供：
- 风险等级（高/中/低）
- 具体位置和代码片段
- 修复建议和示例代码
```

### 示例 2: 性能优化审查

```markdown
# {project_name} 性能优化审查

**MR 信息**
- ID: #{mr_iid}
- 作者: {author}
- 标题: {title}
- 变更: {file_count} 个文件，{changes_count} 行代码

## 性能审查要点

### 1. 数据库性能
- [ ] 是否有 N+1 查询问题
- [ ] 是否缺少必要的索引
- [ ] 是否有不必要的全表扫描
- [ ] 是否合理使用了查询缓存

### 2. 算法效率
- [ ] 时间复杂度是否合理
- [ ] 空间复杂度是否可以优化
- [ ] 是否有重复计算可以优化

### 3. 资源使用
- [ ] 是否有内存泄漏风险
- [ ] 文件/网络资源是否正确关闭
- [ ] 是否有不必要的资源占用

请提供具体的性能优化建议和预期收益。
```

### 示例 3: 代码规范审查

```markdown
请对项目 {project_name} 的 MR #{mr_iid} 进行代码规范审查。

作者：{author}
标题：{title}

重点检查：
1. 命名规范：变量、函数、类名是否符合团队规范
2. 代码格式：缩进、换行、空格是否统一
3. 注释质量：是否有必要的注释，注释是否清晰
4. 函数设计：单一职责原则，函数长度是否合理
5. 错误处理：异常捕获是否完整，错误信息是否明确

对于不符合规范的代码，请提供修改建议。
```

## 🧪 测试验证

运行测试脚本验证功能：

```bash
cd backend
python test_prompt_feature.py
```

测试覆盖：
- ✓ 创建/更新项目
- ✓ 启用 webhook 事件
- ✓ 创建自定义 prompt 配置
- ✓ 测试变量占位符替换
- ✓ 验证渲染结果

## 🎯 最佳实践

### 1. Prompt 编写建议

- **明确审查目标**：清楚地说明希望 AI 关注什么
- **结构化内容**：使用 Markdown 格式，清晰分节
- **具体示例**：提供期望的输出格式示例
- **合理使用占位符**：让 prompt 更动态、更个性化

### 2. 占位符使用技巧

```markdown
# 好的实践
作者 {author} 提交了 MR #{mr_iid}，请审查 {file_count} 个文件的变更。

# 不好的实践（过度使用）
{project_name}{project_name}{project_name} 请审查...
```

### 3. 性能优化建议

- prompt 长度建议控制在 2000 字符以内
- 避免在 prompt 中包含大量重复内容
- 合理使用变量占位符，避免硬编码

## 🔍 故障排查

### 问题 1: Prompt 没有生效

**可能原因**:
- `use_custom` 开关未打开
- prompt 配置未保存
- 项目未启用对应的 webhook 事件

**解决方法**:
1. 检查项目详情页的"审查提示词"标签
2. 确认开关已打开且 prompt 已保存
3. 检查"Webhook事件"标签，确认事件已启用

### 问题 2: 变量没有被替换

**可能原因**:
- 占位符拼写错误（区分大小写）
- MR 信息不完整

**解决方法**:
1. 检查占位符是否拼写正确：`{project_name}` 而非 `{Project_Name}`
2. 查看审查日志，确认 MR 信息是否完整
3. 使用 `test_prompt_feature.py` 测试渲染逻辑

### 问题 3: 自定义 prompt 过长导致错误

**可能原因**:
- prompt 超过了 LLM 的 token 限制

**解决方法**:
1. 精简 prompt 内容，控制在 2000 字符以内
2. 只保留最关键的审查要点
3. 使用更精炼的语言表达

## 📊 数据统计

可以通过以下查询了解系统使用情况：

```sql
-- 统计有多少项目使用了自定义 prompt
SELECT COUNT(DISTINCT project_id)
FROM project_webhook_event_prompts
WHERE use_custom = TRUE;

-- 查看最常用的事件类型
SELECT e.name, COUNT(*) as usage_count
FROM project_webhook_event_prompts p
JOIN webhook_event_rules e ON p.event_rule_id = e.id
WHERE p.use_custom = TRUE
GROUP BY e.name
ORDER BY usage_count DESC;

-- 查看平均 prompt 长度
SELECT AVG(LENGTH(custom_prompt)) as avg_length
FROM project_webhook_event_prompts
WHERE use_custom = TRUE AND custom_prompt != '';
```

## 🚀 未来扩展

### 可能的增强功能

1. **Prompt 模板库**
   - 提供预设的 prompt 模板供用户选择
   - 支持模板的导入/导出

2. **Prompt 版本管理**
   - 记录 prompt 的修改历史
   - 支持回滚到历史版本

3. **A/B 测试**
   - 支持为同一事件配置多个 prompt
   - 自动轮换测试不同 prompt 的效果

4. **AI 辅助优化**
   - 基于审查结果优化 prompt
   - 提供 prompt 改进建议

5. **更多占位符**
   - 支持更复杂的变量表达式
   - 支持条件判断和循环

## 📝 更新日志

### v1.0.1 (2025-01-11)

- 🐛 **[关键修复]** 修复 `LLMService.review_code()` 缺少 `custom_prompt` 参数的问题
- ✅ 添加完整的集成测试 (`test_prompt_integration.py`)
- 📝 更新文档，补充故障排查信息

**修复详情**:
```python
# 修复前
def review_code(self, code_context, mr_info=None, repo_path=None, commit_range=None):
    # 无法接收外部传入的 custom_prompt

# 修复后
def review_code(self, code_context, mr_info=None, repo_path=None, commit_range=None, custom_prompt=None):
    # 支持外部传入的 custom_prompt
    # 优先级: custom_prompt > 基于 mr_info 构建的默认 prompt
```

### v1.0.0 (2025-01-10)

- ✨ 新增项目级 webhook 事件自定义 prompt 功能
- ✨ 支持 10 个常用变量占位符
- ✨ 前端新增"审查提示词"配置界面
- ✨ 自动为启用的事件创建空配置
- 🐛 修复 prompt 渲染时的特殊字符处理问题
- 📝 完善功能文档和使用示例

---

**开发者**: Claude Code Assistant
**最后更新**: 2025-01-11
**当前版本**: 1.0.1
