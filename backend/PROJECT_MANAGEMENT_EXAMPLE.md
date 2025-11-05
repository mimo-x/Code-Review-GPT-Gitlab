# 项目管理功能使用示例

## 快速示例

### 示例 1: 新项目自动发现

**场景**: 一个新的 GitLab 项目首次创建 Merge Request

**Webhook Payload** (简化):
```json
{
    "object_kind": "merge_request",
    "project": {
        "id": 123,
        "name": "awesome-app",
        "path_with_namespace": "mycompany/awesome-app",
        "web_url": "https://gitlab.com/mycompany/awesome-app",
        "namespace": "mycompany"
    },
    "object_attributes": {
        "iid": 1,
        "action": "open",
        "title": "Add new feature"
    }
}
```

**系统处理流程**:

1. **接收 Webhook**
```
POST /api/webhook/gitlab/
```

2. **检查项目**
```python
# 数据库中不存在 project_id=123
project, created = ProjectService.get_or_create_project(project_data)
# created = True
```

3. **创建项目记录**
```python
Project.objects.create(
    project_id=123,
    project_name="awesome-app",
    project_path="mycompany/awesome-app",
    review_enabled=False,  # 默认禁用
    ...
)
```

4. **日志输出**
```
INFO: 🆕 New project added: awesome-app (ID: 123) - Review disabled by default
INFO: ⏸️  Review is disabled for project 123. Skipping code review.
```

5. **Webhook 响应**
```json
{
    "status": "skipped",
    "message": "Code review is disabled for this project. Enable it in project settings to start reviewing."
}
```

---

### 示例 2: 查看所有项目

```bash
curl http://localhost:8000/api/webhook/projects/
```

**响应**:
```json
{
    "status": "success",
    "count": 3,
    "projects": [
        {
            "project_id": 123,
            "project_name": "awesome-app",
            "project_path": "mycompany/awesome-app",
            "review_enabled": false,
            "created_at": "2025-01-04T10:00:00Z",
            "last_webhook_at": "2025-01-04T10:05:00Z"
        },
        {
            "project_id": 456,
            "project_name": "api-service",
            "project_path": "mycompany/api-service",
            "review_enabled": true,
            "created_at": "2025-01-03T15:00:00Z",
            "last_webhook_at": "2025-01-04T09:30:00Z"
        },
        {
            "project_id": 789,
            "project_name": "frontend-app",
            "project_path": "mycompany/frontend-app",
            "review_enabled": false,
            "created_at": "2025-01-02T12:00:00Z",
            "last_webhook_at": "2025-01-04T08:15:00Z"
        }
    ]
}
```

---

### 示例 3: 启用项目代码审查

**步骤 1: 查看项目状态**
```bash
curl http://localhost:8000/api/webhook/projects/123/
```

**响应**:
```json
{
    "status": "success",
    "project": {
        "project_id": 123,
        "project_name": "awesome-app",
        "review_enabled": false,  // 当前禁用
        ...
    }
}
```

**步骤 2: 启用代码审查**
```bash
curl -X POST http://localhost:8000/api/webhook/projects/123/enable/
```

**响应**:
```json
{
    "status": "success",
    "message": "Code review enabled for project awesome-app",
    "project": {
        "project_id": 123,
        "project_name": "awesome-app",
        "review_enabled": true,  // 已启用
        ...
    }
}
```

**日志输出**:
```
INFO: Review enabled for project: awesome-app (ID: 123)
```

**步骤 3: 验证**
```bash
curl http://localhost:8000/api/webhook/projects/123/
```

现在 `review_enabled` 应该是 `true`

---

### 示例 4: 启用后再次触发 MR

**场景**: 同一个项目再次创建 MR

**Webhook Payload**:
```json
{
    "object_kind": "merge_request",
    "project": {
        "id": 123,
        "name": "awesome-app",
        ...
    },
    "object_attributes": {
        "iid": 2,
        "action": "open",
        "title": "Fix bug"
    }
}
```

**系统处理流程**:

1. **接收 Webhook**
```
POST /api/webhook/gitlab/
```

2. **检查项目**
```python
project, created = ProjectService.get_or_create_project(project_data)
# created = False (项目已存在)
# project.review_enabled = True
```

3. **检查审查状态**
```python
if ProjectService.is_review_enabled(project_id):
    # 返回 True，继续处理
```

4. **执行代码审查**
```
- 获取 MR 变更
- 调用 LLM 审查代码
- 发布 GitLab 评论
```

5. **日志输出**
```
INFO: Processing merge request: Project 123, MR #2
INFO: Review completed for MR #2
```

6. **Webhook 响应**
```json
{
    "status": "success",
    "message": "Review process started"
}
```

---

### 示例 5: 配置项目文件过滤

```bash
curl -X PATCH http://localhost:8000/api/webhook/projects/123/update/ \
  -H "Content-Type: application/json" \
  -d '{
    "exclude_file_types": [".py", ".java", ".go"],
    "ignore_file_patterns": ["test_*.py", "*.test.js"]
  }'
```

**响应**:
```json
{
    "status": "success",
    "message": "Project settings updated successfully",
    "project": {
        "project_id": 123,
        "project_name": "awesome-app",
        "review_enabled": true,
        "exclude_file_types": [".py", ".java", ".go"],
        "ignore_file_patterns": ["test_*.py", "*.test.js"],
        ...
    }
}
```

---

### 示例 6: 查看项目统计

```bash
curl http://localhost:8000/api/webhook/projects/stats/
```

**响应**:
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

---

### 示例 7: 只查看已启用审查的项目

```bash
curl http://localhost:8000/api/webhook/projects/?review_enabled=true
```

**响应**:
```json
{
    "status": "success",
    "count": 3,
    "projects": [
        {
            "project_id": 456,
            "project_name": "api-service",
            "review_enabled": true,
            ...
        },
        {
            "project_id": 234,
            "project_name": "backend-service",
            "review_enabled": true,
            ...
        },
        {
            "project_id": 567,
            "project_name": "ml-model",
            "review_enabled": true,
            ...
        }
    ]
}
```

---

### 示例 8: 禁用项目审查

```bash
curl -X POST http://localhost:8000/api/webhook/projects/123/disable/
```

**响应**:
```json
{
    "status": "success",
    "message": "Code review disabled for project awesome-app",
    "project": {
        "project_id": 123,
        "review_enabled": false,
        ...
    }
}
```

---

### 示例 9: 批量管理脚本

#### Python 脚本示例

```python
import requests

BASE_URL = "http://localhost:8000/api/webhook"

# 获取所有项目
response = requests.get(f"{BASE_URL}/projects/")
projects = response.json()['projects']

print(f"Total projects: {len(projects)}")

# 启用所有 Python 项目的审查
for project in projects:
    if 'python' in project['project_name'].lower():
        project_id = project['project_id']
        print(f"Enabling review for {project['project_name']}...")

        requests.post(f"{BASE_URL}/projects/{project_id}/enable/")

# 配置特定项目
requests.patch(
    f"{BASE_URL}/projects/123/update/",
    json={
        "review_enabled": True,
        "exclude_file_types": [".py", ".java"],
        "ignore_file_patterns": ["*_test.py"]
    }
)
```

#### Bash 脚本示例

```bash
#!/bin/bash

BASE_URL="http://localhost:8000/api/webhook"

# 获取所有禁用审查的项目
disabled_projects=$(curl -s "$BASE_URL/projects/?review_enabled=false" | \
    jq -r '.projects[].project_id')

echo "Disabled projects: $disabled_projects"

# 逐个询问是否启用
for project_id in $disabled_projects; do
    # 获取项目信息
    project_name=$(curl -s "$BASE_URL/projects/$project_id/" | \
        jq -r '.project.project_name')

    read -p "Enable review for $project_name? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Enabling..."
        curl -X POST "$BASE_URL/projects/$project_id/enable/"
        echo
    fi
done
```

---

### 示例 10: Django Admin 管理

访问: `http://localhost:8000/admin/webhook/project/`

**操作示例**:

1. **查看项目列表**
   - 显示所有项目
   - 可按 review_enabled 过滤
   - 可按项目名搜索

2. **编辑项目**
   - 点击项目名称进入编辑页面
   - 修改 review_enabled 复选框
   - 编辑文件过滤规则
   - 保存

3. **批量操作**
   - 选中多个项目
   - 选择操作: "Enable review" 或 "Disable review"
   - 点击 "Go"

---

## 实际工作流示例

### 场景: 公司有 20 个 GitLab 项目

#### 第 1 阶段: 发现所有项目

1. **配置 Webhooks**
   - 在 GitLab 组级别或每个项目配置 Webhook
   - URL: `http://your-server:8000/api/webhook/gitlab/`

2. **触发初始事件**
   - 方式 A: 在每个项目创建一个测试 MR
   - 方式 B: 等待自然的 MR 创建
   - 方式 C: 重放历史 Webhook 事件

3. **验证项目已创建**
```bash
curl http://localhost:8000/api/webhook/projects/ | jq '.count'
# 输出: 20
```

#### 第 2 阶段: 选择性启用审查

1. **查看统计**
```bash
curl http://localhost:8000/api/webhook/projects/stats/
# {
#   "total_projects": 20,
#   "review_enabled": 0,
#   "review_disabled": 20
# }
```

2. **先启用测试项目**
```bash
# 项目ID: 999 (test-project)
curl -X POST http://localhost:8000/api/webhook/projects/999/enable/
```

3. **观察几天，调整配置**
```bash
curl -X PATCH http://localhost:8000/api/webhook/projects/999/update/ \
  -H "Content-Type: application/json" \
  -d '{
    "exclude_file_types": [".py", ".java"],
    "ignore_file_patterns": ["*_test.py", "migrations/*.py"]
  }'
```

4. **逐步启用其他项目**
```bash
# 启用核心项目
for id in 123 456 789; do
    curl -X POST http://localhost:8000/api/webhook/projects/$id/enable/
done
```

5. **最终验证**
```bash
curl http://localhost:8000/api/webhook/projects/stats/
# {
#   "total_projects": 20,
#   "review_enabled": 10,
#   "review_disabled": 10
# }
```

#### 第 3 阶段: 持续运营

- 定期查看项目统计
- 根据反馈调整配置
- 新项目自动发现并按需启用

---

## 常见问题示例

### Q: 如何快速启用所有项目？

```bash
#!/bin/bash
projects=$(curl -s http://localhost:8000/api/webhook/projects/ | \
    jq -r '.projects[].project_id')

for pid in $projects; do
    echo "Enabling project $pid..."
    curl -X POST http://localhost:8000/api/webhook/projects/$pid/enable/
done
```

### Q: 如何只对特定组的项目启用？

```python
import requests

response = requests.get("http://localhost:8000/api/webhook/projects/")
projects = response.json()['projects']

# 只启用 'backend' 组的项目
for project in projects:
    if project['namespace'] == 'backend':
        requests.post(
            f"http://localhost:8000/api/webhook/projects/{project['project_id']}/enable/"
        )
```

### Q: 如何导出项目配置？

```bash
curl -s http://localhost:8000/api/webhook/projects/ | \
    jq '.projects[] | {
        id: .project_id,
        name: .project_name,
        enabled: .review_enabled
    }' > projects_config.json
```

---

## 测试示例

### 使用 curl 测试完整流程

```bash
#!/bin/bash

# 1. 查看初始状态
echo "=== 初始项目列表 ==="
curl http://localhost:8000/api/webhook/projects/

# 2. 模拟 Webhook（触发项目创建）
echo -e "\n=== 触发 Webhook ==="
curl -X POST http://localhost:8000/api/webhook/gitlab/ \
  -H "Content-Type: application/json" \
  -d @test_webhook_payload.json

# 3. 查看新项目
echo -e "\n=== 查看新项目 ==="
curl http://localhost:8000/api/webhook/projects/123/

# 4. 启用审查
echo -e "\n=== 启用代码审查 ==="
curl -X POST http://localhost:8000/api/webhook/projects/123/enable/

# 5. 再次查看
echo -e "\n=== 验证已启用 ==="
curl http://localhost:8000/api/webhook/projects/123/

# 6. 查看统计
echo -e "\n=== 项目统计 ==="
curl http://localhost:8000/api/webhook/projects/stats/
```

---

希望这些示例能帮助您理解和使用项目管理功能！🎉
