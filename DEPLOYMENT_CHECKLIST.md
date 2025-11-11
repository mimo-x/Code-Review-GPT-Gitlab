# 项目级自定义 Prompt 功能部署清单

## ✅ 部署前检查

### 1. 代码变更确认

- [x] **后端模型**: `ProjectWebhookEventPrompt` 模型已创建
- [x] **数据库迁移**: `0007_projectwebhookeventprompt_and_more.py` 已生成
- [x] **后端接口**: 2 个新接口已实现
  - `GET /api/webhook/projects/{id}/webhook-event-prompts/`
  - `POST /api/webhook/projects/{id}/webhook-event-prompts/update/`
- [x] **业务逻辑**: 代码审查流程已集成自定义 prompt 支持
- [x] **前端界面**: "审查提示词" Tab 已添加
- [x] **前端 API**: 2 个 API 函数已添加

### 2. 文件清单

**后端文件 (已修改)**:
```
backend/apps/webhook/models.py                 # 新增 ProjectWebhookEventPrompt 模型
backend/apps/webhook/serializers.py           # 新增 2 个序列化器
backend/apps/webhook/views.py                 # 新增 2 个视图函数，修改审查逻辑
backend/apps/webhook/urls.py                  # 新增 2 个路由
backend/apps/llm/services.py                  # 修改 review_code 方法签名
backend/apps/webhook/migrations/0007_*.py     # 数据库迁移文件
```

**前端文件 (已修改)**:
```
frontend/src/api/index.ts                     # 新增 2 个 API 函数
frontend/src/views/ProjectDetail.vue          # 新增 Tab 和相关逻辑
```

**测试和文档**:
```
backend/test_prompt_feature.py                # 功能测试脚本
backend/test_prompt_integration.py            # 集成测试脚本
CUSTOM_PROMPT_FEATURE.md                      # 功能文档
DEPLOYMENT_CHECKLIST.md                       # 本文件
```

## 🚀 部署步骤

### 步骤 1: 备份数据库

```bash
# SQLite 数据库备份
cp backend/db.sqlite3 backend/db.sqlite3.backup.$(date +%Y%m%d_%H%M%S)

# 或者使用 Django 导出
python manage.py dumpdata > backup_$(date +%Y%m%d_%H%M%S).json
```

### 步骤 2: 更新后端代码

```bash
cd backend

# 拉取最新代码
git pull origin feat/project-manage

# 安装依赖（如有新增）
pip install -r requirements.txt

# 运行数据库迁移
python manage.py migrate webhook

# 验证迁移
python manage.py showmigrations webhook
```

**预期输出**:
```
webhook
 [X] 0001_initial
 [X] 0002_...
 [X] 0007_projectwebhookeventprompt_and_more  # 新迁移
```

### 步骤 3: 运行测试

```bash
cd backend

# 运行功能测试
python test_prompt_feature.py

# 运行集成测试
python test_prompt_integration.py
```

**预期输出**: 所有测试应显示 ✓ 通过

### 步骤 4: 启动后端服务

```bash
cd backend

# 开发环境
python manage.py runserver

# 生产环境（示例）
gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

### 步骤 5: 更新前端代码

```bash
cd frontend

# 安装依赖（如有新增）
npm install

# 开发环境
npm run dev

# 生产环境构建
npm run build
```

### 步骤 6: 验证功能

#### 6.1 后端 API 验证

```bash
# 获取项目的 prompt 配置
curl -X GET "http://localhost:8000/api/webhook/projects/1/webhook-event-prompts/" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 更新 prompt 配置
curl -X POST "http://localhost:8000/api/webhook/projects/1/webhook-event-prompts/update/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "event_rule_id": 1,
    "custom_prompt": "测试 prompt",
    "use_custom": true
  }'
```

#### 6.2 前端界面验证

1. 登录系统
2. 进入任意项目详情页
3. 点击"审查提示词"Tab
4. 确认界面正常显示
5. 尝试编辑和保存 prompt

#### 6.3 端到端验证

1. 为测试项目配置自定义 prompt
2. 在 GitLab 中创建一个 MR
3. 触发 webhook 事件
4. 检查审查日志，确认使用了自定义 prompt
5. 验证变量占位符被正确替换

## 🔍 验证点清单

### 数据库层面

- [ ] `project_webhook_event_prompts` 表已创建
- [ ] 表结构符合设计（包含所有字段）
- [ ] 唯一约束 `(project_id, event_rule_id)` 生效

**验证命令**:
```bash
python manage.py dbshell
.schema project_webhook_event_prompts
```

### API 层面

- [ ] GET 接口返回正确的数据结构
- [ ] POST 接口可以创建/更新配置
- [ ] 为未配置的事件自动创建空配置
- [ ] 错误处理正确（404、500 等）

### 业务逻辑层面

- [ ] 自定义 prompt 能够传递到 `LLMService.review_code()`
- [ ] 变量占位符正确替换
- [ ] 未配置时使用系统默认 prompt
- [ ] 日志中记录 prompt 来源（自定义/默认）

### 前端界面层面

- [ ] "审查提示词" Tab 正常显示
- [ ] 配置卡片正确渲染
- [ ] 开关功能正常
- [ ] 编辑器可以正常输入和保存
- [ ] 占位符提示正确显示
- [ ] 保存成功/失败有提示

## ⚠️ 已知问题和限制

### 1. Prompt 长度限制

**问题**: 非常长的 prompt 可能超过 LLM 的 token 限制

**解决方案**:
- 建议 prompt 长度控制在 2000 字符以内
- 可以在前端添加字符计数提示

### 2. 并发更新

**问题**: 多人同时编辑同一项目的 prompt 可能导致覆盖

**解决方案**:
- 当前版本使用"后保存者胜"策略
- 未来可以添加版本控制或锁机制

### 3. 变量值为空

**问题**: 某些 MR 可能缺少部分信息（如 description）

**解决方案**:
- 占位符会被替换为空字符串
- 建议在 prompt 中谨慎使用可能为空的变量

## 🐛 故障排查

### 问题 1: 迁移失败

**症状**: `python manage.py migrate` 报错

**排查步骤**:
1. 检查数据库文件权限
2. 查看迁移文件是否损坏
3. 尝试回滚到上一个迁移
4. 查看详细错误信息

**解决方法**:
```bash
# 回滚迁移
python manage.py migrate webhook 0006

# 重新运行迁移
python manage.py migrate webhook
```

### 问题 2: API 返回 500 错误

**症状**: 调用 API 时返回 500 错误

**排查步骤**:
1. 查看后端日志 (`python manage.py runserver` 的输出)
2. 检查数据库连接
3. 验证项目 ID 是否存在
4. 查看 `apps/webhook/views.py` 中的错误日志

**解决方法**:
- 确保项目存在且已启用 webhook 事件
- 检查事件规则 ID 是否有效

### 问题 3: 自定义 prompt 没有生效

**症状**: MR 审查仍使用默认 prompt

**排查步骤**:
1. 确认 `use_custom` 开关已打开
2. 检查数据库中配置是否保存
3. 查看审查日志中的 prompt 来源信息
4. 验证 matched_rule 是否正确传递

**解决方法**:
```bash
# 检查数据库配置
python manage.py shell
>>> from apps.webhook.models import ProjectWebhookEventPrompt
>>> configs = ProjectWebhookEventPrompt.objects.filter(use_custom=True)
>>> for c in configs:
...     print(f"Project {c.project_id}, Event {c.event_rule.name}, Use Custom: {c.use_custom}")
```

### 问题 4: 变量没有被替换

**症状**: prompt 中的 `{project_name}` 等仍然保持原样

**排查步骤**:
1. 检查占位符拼写（区分大小写）
2. 查看 MR 信息是否完整
3. 检查 `render_prompt()` 方法逻辑
4. 查看后端日志

**解决方法**:
```python
# 测试渲染逻辑
python manage.py shell
>>> from apps.webhook.models import ProjectWebhookEventPrompt
>>> prompt = ProjectWebhookEventPrompt.objects.first()
>>> test_context = {'project_name': 'Test', 'author': 'John'}
>>> print(prompt.render_prompt(test_context))
```

## 📊 性能考虑

### 数据库查询优化

当前实现使用了以下优化：

1. **select_related**: 获取 prompt 配置时预加载 event_rule
```python
ProjectWebhookEventPrompt.objects.filter(...).select_related('event_rule')
```

2. **索引**: 在 `(project_id, event_rule_id)` 和 `use_custom` 字段上创建了索引

3. **缓存建议**: 可以考虑缓存项目的 prompt 配置，减少数据库查询

### 预期性能影响

- **额外数据库查询**: 每次 MR 审查增加 1 次查询（获取自定义 prompt）
- **内存开销**: 每个 prompt 配置约 2-5KB
- **处理时间**: prompt 渲染约 < 1ms

## 🔐 安全考虑

### 输入验证

- ✅ event_rule_id 验证存在性
- ✅ 项目权限验证（通过 project_id）
- ⚠️ 建议添加: prompt 内容长度限制
- ⚠️ 建议添加: 恶意内容过滤

### 建议增强

```python
# 在 serializer 中添加验证
class ProjectWebhookEventPromptUpdateSerializer(serializers.Serializer):
    custom_prompt = serializers.CharField(
        allow_blank=True,
        required=False,
        max_length=5000,  # 限制最大长度
        default=''
    )
```

## 📈 监控建议

### 关键指标

1. **使用率**: 有多少项目启用了自定义 prompt
```sql
SELECT COUNT(DISTINCT project_id)
FROM project_webhook_event_prompts
WHERE use_custom = TRUE;
```

2. **平均 prompt 长度**
```sql
SELECT AVG(LENGTH(custom_prompt))
FROM project_webhook_event_prompts
WHERE use_custom = TRUE;
```

3. **最常用的事件类型**
```sql
SELECT e.name, COUNT(*) as count
FROM project_webhook_event_prompts p
JOIN webhook_event_rules e ON p.event_rule_id = e.id
WHERE p.use_custom = TRUE
GROUP BY e.name
ORDER BY count DESC;
```

### 日志监控

关键日志消息：
- `使用外部传入的自定义 Prompt` - 自定义 prompt 生效
- `使用系统默认 Prompt 构建逻辑` - 使用默认 prompt
- `获取自定义 Prompt 失败` - 配置读取错误

## ✅ 部署后验证

完成部署后，运行以下命令进行完整验证：

```bash
cd backend

# 1. 运行所有测试
python test_prompt_feature.py
python test_prompt_integration.py

# 2. 检查迁移状态
python manage.py showmigrations | grep webhook

# 3. 验证 API 可访问
curl -X GET "http://localhost:8000/api/webhook/projects/1/webhook-event-prompts/"

# 4. 检查服务日志
tail -f logs/app.log | grep "custom.*prompt"
```

**预期结果**: 所有测试通过，API 返回 200，日志无错误

## 📞 支持和反馈

如遇到问题，请提供以下信息：

1. 错误消息和堆栈跟踪
2. 相关的日志片段
3. 复现步骤
4. 数据库状态（如适用）

---

**部署完成日期**: _________
**部署人员**: _________
**验证人员**: _________
**状态**: [ ] 成功 [ ] 部分成功 [ ] 失败

**备注**:
