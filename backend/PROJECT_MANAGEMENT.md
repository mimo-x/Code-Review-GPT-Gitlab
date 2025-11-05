# 项目管理功能说明

## 功能概述

当 Webhook 接收到 GitLab 事件时，系统会自动检查数据库中是否存在该项目的记录。如果不存在，则自动创建项目记录，**默认禁用代码审查功能**。

## 核心特性

### 1. 自动项目发现
- ✅ 接收到首个 Webhook 时自动创建项目记录
- ✅ 默认禁用代码审查（review_enabled = False）
- ✅ 记录项目基本信息（名称、路径、URL 等）
- ✅ 记录最后 Webhook 接收时间

### 2. 项目状态管理
- ✅ 启用/禁用代码审查功能
- ✅ 配置自动审查选项
- ✅ 自定义文件过滤规则
- ✅ 查看项目统计信息

### 3. 灵活配置
- ✅ 每个项目独立配置
- ✅ 支持批量查询和过滤
- ✅ RESTful API 管理接口

## 数据模型

### Project 模型

```python
class Project(models.Model):
    project_id          # GitLab 项目 ID（唯一）
    project_name        # 项目名称
    project_path        # 项目路径
    project_url         # 项目 URL
    namespace           # 命名空间

    # 审查设置
    review_enabled      # 是否启用代码审查（默认: False）
    auto_review_on_mr   # MR 时自动审查（默认: True）

    # 文件过滤
    exclude_file_types  # 要审查的文件类型列表
    ignore_file_patterns # 忽略的文件模式列表

    # 元数据
    gitlab_data         # GitLab 完整数据（JSON）
    created_at          # 创建时间
    updated_at          # 更新时间
    last_webhook_at     # 最后接收 Webhook 时间
```

## API 端点

### 1. 列出所有项目

```http
GET /api/webhook/projects/
```

**查询参数**:
- `review_enabled` (可选): `true` 或 `false` - 过滤启用/禁用审查的项目

**响应示例**:
```json
{
    "status": "success",
    "count": 10,
    "projects": [
        {
            "project_id": 123,
            "project_name": "my-awesome-project",
            "project_path": "group/my-awesome-project",
            "project_url": "https://gitlab.com/group/my-awesome-project",
            "namespace": "group",
            "review_enabled": false,
            "auto_review_on_mr": true,
            "exclude_file_types": [],
            "ignore_file_patterns": [],
            "created_at": "2025-01-04T10:00:00Z",
            "updated_at": "2025-01-04T10:00:00Z",
            "last_webhook_at": "2025-01-04T11:30:00Z"
        }
    ]
}
```

### 2. 获取项目详情

```http
GET /api/webhook/projects/{project_id}/
```

**响应示例**:
```json
{
    "status": "success",
    "project": {
        "project_id": 123,
        "project_name": "my-awesome-project",
        "review_enabled": false,
        ...
    }
}
```

### 3. 更新项目设置

```http
PATCH /api/webhook/projects/{project_id}/update/
Content-Type: application/json

{
    "review_enabled": true,
    "auto_review_on_mr": true,
    "exclude_file_types": [".py", ".java", ".go"],
    "ignore_file_patterns": ["test_*.py", "*.test.js"]
}
```

**响应示例**:
```json
{
    "status": "success",
    "message": "Project settings updated successfully",
    "project": { ... }
}
```

### 4. 启用项目代码审查

```http
POST /api/webhook/projects/{project_id}/enable/
```

**响应示例**:
```json
{
    "status": "success",
    "message": "Code review enabled for project my-awesome-project",
    "project": { ... }
}
```

### 5. 禁用项目代码审查

```http
POST /api/webhook/projects/{project_id}/disable/
```

**响应示例**:
```json
{
    "status": "success",
    "message": "Code review disabled for project my-awesome-project",
    "project": { ... }
}
```

### 6. 获取项目统计

```http
GET /api/webhook/projects/stats/
```

**响应示例**:
```json
{
    "status": "success",
    "stats": {
        "total_projects": 10,
        "review_enabled": 3,
        "review_disabled": 7
    }
}
```

## 使用流程

### 场景 1: 新项目首次触发 Webhook

1. GitLab 项目触发 Webhook（如创建 MR）
2. 系统接收 Webhook 事件
3. 检查数据库：项目不存在
4. **自动创建项目记录，review_enabled = False**
5. 记录 Webhook 日志
6. **跳过代码审查**（因为未启用）
7. 返回响应: `"status": "skipped", "message": "Code review is disabled..."`

**日志输出**:
```
INFO: 🆕 New project added: my-awesome-project (ID: 123) - Review disabled by default
INFO: ⏸️  Review is disabled for project 123. Skipping code review.
```

### 场景 2: 启用项目代码审查

**方式 A: 通过 API 启用**
```bash
curl -X POST http://localhost:8000/api/webhook/projects/123/enable/
```

**方式 B: 通过 API 更新设置**
```bash
curl -X PATCH http://localhost:8000/api/webhook/projects/123/update/ \
  -H "Content-Type: application/json" \
  -d '{"review_enabled": true}'
```

### 场景 3: 启用后的 Webhook 处理

1. GitLab 项目触发 Webhook
2. 系统接收 Webhook 事件
3. 检查数据库：项目存在，review_enabled = True
4. 更新 last_webhook_at
5. **执行代码审查**
6. 发布 GitLab 评论
7. 返回响应: `"status": "success", "message": "Review process started"`

## 管理示例

### 查看所有项目

```bash
# 查看所有项目
curl http://localhost:8000/api/webhook/projects/

# 只查看启用审查的项目
curl http://localhost:8000/api/webhook/projects/?review_enabled=true

# 只查看禁用审查的项目
curl http://localhost:8000/api/webhook/projects/?review_enabled=false
```

### 启用特定项目的代码审查

```bash
# 获取项目 ID（从 GitLab 或首次 Webhook 日志中）
PROJECT_ID=123

# 启用代码审查
curl -X POST http://localhost:8000/api/webhook/projects/$PROJECT_ID/enable/
```

### 批量启用代码审查（脚本示例）

```bash
#!/bin/bash
# enable_all_projects.sh

# 获取所有项目
projects=$(curl -s http://localhost:8000/api/webhook/projects/ | jq -r '.projects[].project_id')

# 遍历并启用
for project_id in $projects; do
    echo "Enabling review for project $project_id..."
    curl -X POST http://localhost:8000/api/webhook/projects/$project_id/enable/
    sleep 1
done
```

### 配置项目文件过滤

```bash
curl -X PATCH http://localhost:8000/api/webhook/projects/123/update/ \
  -H "Content-Type: application/json" \
  -d '{
    "review_enabled": true,
    "exclude_file_types": [".py", ".java", ".go", ".ts"],
    "ignore_file_patterns": ["*_test.py", "*.test.js", "mock_*.py"]
  }'
```

## Django Admin 管理

访问 Django Admin 界面管理项目：

```
http://localhost:8000/admin/webhook/project/
```

功能：
- ✅ 查看所有项目列表
- ✅ 搜索和过滤项目
- ✅ 批量启用/禁用代码审查
- ✅ 编辑项目设置
- ✅ 查看项目详情和 GitLab 元数据

## 数据库查询示例

### 使用 Django Shell

```python
python manage.py shell

from apps.webhook.models import Project

# 查询所有项目
Project.objects.all()

# 查询启用审查的项目
Project.objects.filter(review_enabled=True)

# 查询特定项目
project = Project.objects.get(project_id=123)
print(f"Project: {project.project_name}")
print(f"Review Enabled: {project.review_enabled}")
print(f"Last Webhook: {project.last_webhook_at}")

# 启用代码审查
project.review_enabled = True
project.save()

# 统计
total = Project.objects.count()
enabled = Project.objects.filter(review_enabled=True).count()
print(f"Total: {total}, Enabled: {enabled}")
```

### MongoDB 直接查询

```bash
# 连接到 MongoDB
docker-compose exec mongodb mongosh code_review_gpt

# 查询所有项目
db.projects.find()

# 查询启用审查的项目
db.projects.find({ review_enabled: true })

# 统计
db.projects.countDocuments()
db.projects.countDocuments({ review_enabled: true })

# 更新项目
db.projects.updateOne(
  { project_id: 123 },
  { $set: { review_enabled: true } }
)
```

## 最佳实践

### 1. 项目发现阶段（推荐）

1. 配置好 GitLab Webhooks
2. 让各个项目触发一次 Webhook（创建 MR 或其他事件）
3. 系统自动发现并创建所有项目记录
4. 查看项目列表：`GET /api/webhook/projects/`
5. 根据需要选择性启用代码审查

### 2. 逐步启用策略

```bash
# 先在测试项目上启用
curl -X POST http://localhost:8000/api/webhook/projects/TEST_PROJECT_ID/enable/

# 观察效果，调整配置
# ...

# 再启用生产项目
curl -X POST http://localhost:8000/api/webhook/projects/PROD_PROJECT_ID/enable/
```

### 3. 项目分组管理

- **核心项目**: 启用审查 + 严格规则
- **测试项目**: 启用审查 + 宽松规则
- **文档项目**: 禁用审查
- **工具项目**: 按需启用

### 4. 监控和维护

定期检查：
- 项目统计：`GET /api/webhook/projects/stats/`
- 最近活跃项目：根据 `last_webhook_at` 排序
- 审查成功率：查看 WebhookLog 和 MergeRequestReview

## 故障排查

### 问题 1: 项目一直没有被创建

**检查**:
- GitLab Webhook 配置是否正确
- Webhook URL 是否可达
- 查看 Django 日志：`docker-compose logs -f django`

### 问题 2: 启用审查后仍然跳过

**检查**:
```python
from apps.webhook.models import Project

project = Project.objects.get(project_id=YOUR_PROJECT_ID)
print(f"Review Enabled: {project.review_enabled}")  # 应该是 True
```

### 问题 3: 无法更新项目设置

**检查**:
- API 请求格式是否正确（Content-Type: application/json）
- 字段名称是否正确
- 查看 API 响应的 errors 字段

## 未来功能

- [ ] 项目分组和标签
- [ ] 审查规则模板
- [ ] 项目级别的 LLM 配置
- [ ] 审查历史和统计图表
- [ ] 项目审查报告导出
- [ ] Webhook 事件重放

## 相关文档

- [后端 README](./README.md)
- [快速开始](../QUICK_START.md)
- [项目结构](../PROJECT_STRUCTURE.md)
