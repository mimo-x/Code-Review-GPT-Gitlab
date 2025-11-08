# Claude CLI 代码审查功能 - 需求与实现文档

**版本**: 1.0
**日期**: 2025-11-08
**状态**: 已实现

---

## 📋 目录

1. [需求背景](#需求背景)
2. [功能目标](#功能目标)
3. [技术方案](#技术方案)
4. [架构设计](#架构设计)
5. [实现细节](#实现细节)
6. [配置说明](#配置说明)
7. [使用指南](#使用指南)
8. [API 参考](#api-参考)
9. [故障排查](#故障排查)
10. [未来优化](#未来优化)

---

## 需求背景

### 原有方案的局限性

之前的代码审查流程使用 `claude_agent_sdk` 或 `litellm` 库通过 API 方式调用 LLM 进行代码审查，存在以下问题：

1. **上下文有限**：只能传递 diff 内容，缺乏完整的项目结构信息
2. **理解深度不足**：无法理解文件间的依赖关系和项目整体架构
3. **API 限制**：受 token 限制和 API 调用配额影响
4. **提供商依赖**：强依赖特定的 LLM 提供商配置

### 新方案的优势

使用 **Claude CLI** 进行本地化代码审查：

1. ✅ **完整上下文**：克隆整个项目到本地，提供完整的项目结构
2. ✅ **深度理解**：Claude 可以分析文件关系、项目架构和代码模式
3. ✅ **灵活配置**：通过 prompt 自定义审查角度（安全、性能、最佳实践等）
4. ✅ **详细输出**：JSON 格式输出包含耗时、token 使用等详细统计
5. ✅ **提供商无关**：不再依赖特定的 LLM API 配置

### Claude CLI 命令示例

```bash
# 在项目目录中执行
cd /path/to/project
git checkout feature-branch

# 执行代码审查
claude -p "请帮我 code review 最近一次提交的内容，从安全角度分析" --output-format json
```

**输出示例**：

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 41628,
  "duration_api_ms": 67475,
  "num_turns": 3,
  "result": "## 安全审查结果\n\n从安全角度来看，这次提交存在以下**严重安全问题**:\n\n### 🔴 严重安全风险\n\n**1. 敏感信息泄露**...",
  "session_id": "538a7215-9e56-4b6b-a405-a6483ebc3f4e",
  "total_cost_usd": 0.14499105,
  "usage": {
    "input_tokens": 2928,
    "cache_creation_input_tokens": 26453,
    "cache_read_input_tokens": 25951,
    "output_tokens": 1243
  }
}
```

---

## 功能目标

### 核心功能

1. **自动化仓库管理**
   - 接收 GitLab MR Webhook 事件
   - 自动克隆或更新项目仓库到本地
   - 切换到对应的 MR 分支
   - 定期清理过期的本地仓库

2. **Claude CLI 集成**
   - 在本地仓库中执行 `claude` 命令
   - 支持自定义审查 prompt
   - 解析 JSON 格式输出
   - 处理超时和错误

3. **结果解析与存储**
   - 解析 Claude 输出的 JSON 数据
   - 提取问题列表、评分、安全漏洞等
   - 格式化为可读的报告
   - 存储到数据库

4. **通知分发**
   - 将审查结果发送到 GitLab MR 评论
   - 支持多渠道通知（Slack、Feishu、Email 等）

### 非功能需求

- **性能**：仓库克隆使用浅克隆（`--depth 1`）提高速度
- **可靠性**：完善的错误处理和日志记录
- **安全性**：使用 OAuth token 认证，不暴露敏感信息
- **可维护性**：模块化设计，易于扩展和测试

---

## 技术方案

### 核心技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web 框架 | Django + DRF | 后端 API 服务 |
| 数据库 | SQLite / PostgreSQL | 存储审查记录 |
| Git 操作 | subprocess + git CLI | 仓库克隆和管理 |
| LLM 集成 | Claude CLI | 代码审查引擎 |
| 日志系统 | Python logging | 结构化日志 |
| 任务队列 | Threading | 异步处理审查任务 |

### 新增模块

```
backend/apps/review/
├── repository_manager.py      # 仓库克隆和管理
├── claude_cli_service.py      # Claude CLI 调用封装
├── review_result_parser.py    # 结果解析器
└── services.py                # 现有的 GitlabService
```

---

## 架构设计

### 系统架构图

```
┌─────────────┐
│  GitLab MR  │
│   Webhook   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         Django Backend                  │
│  ┌───────────────────────────────────┐ │
│  │  webhook/views.py                 │ │
│  │  - gitlab_webhook()               │ │
│  │  - handle_merge_request()         │ │
│  │  - process_merge_request_review() │ │
│  └────────────┬──────────────────────┘ │
│               │                         │
│               ▼                         │
│  ┌───────────────────────────────────┐ │
│  │  review/repository_manager.py     │ │
│  │  - get_or_clone_repository()      │ │
│  │  - checkout_merge_request()       │ │
│  │  - get_commit_range()             │ │
│  └────────────┬──────────────────────┘ │
│               │                         │
│               ▼                         │
│  ┌───────────────────────────────────┐ │
│  │  review/claude_cli_service.py     │ │
│  │  - review_code()                  │ │
│  │  - execute claude command         │ │
│  │  - parse JSON output              │ │
│  └────────────┬──────────────────────┘ │
│               │                         │
│               ▼                         │
│  ┌───────────────────────────────────┐ │
│  │  review/review_result_parser.py   │ │
│  │  - parse()                        │ │
│  │  - extract_issues()               │ │
│  │  - calculate_score()              │ │
│  └────────────┬──────────────────────┘ │
│               │                         │
│               ▼                         │
│  ┌───────────────────────────────────┐ │
│  │  Database (MergeRequestReview)    │ │
│  │  - review_content                 │ │
│  │  - review_score                   │ │
│  │  - repository_path                │ │
│  └────────────┬──────────────────────┘ │
│               │                         │
└───────────────┼─────────────────────────┘
                │
                ▼
┌───────────────────────────────┐
│  Notification Dispatcher      │
│  - GitLab Comment             │
│  - Slack / Feishu / Email     │
└───────────────────────────────┘
```

### 数据流

```
1. GitLab Webhook → Django
2. 创建 MergeRequestReview 记录（status=pending）
3. 启动异步线程处理
4. RepositoryManager: 克隆/更新仓库
5. RepositoryManager: 切换到 MR 分支
6. ClaudeCliService: 执行 claude 命令
7. ReviewResultParser: 解析 JSON 输出
8. 更新 MergeRequestReview 记录（status=completed）
9. NotificationDispatcher: 发送通知
```

---

## 实现细节

### 1. RepositoryManager (`repository_manager.py`)

**职责**：管理本地 Git 仓库的生命周期

#### 核心方法

```python
class RepositoryManager:
    def __init__(self, request_id=None):
        self.request_id = request_id
        self.base_path = settings.REPOSITORY_BASE_PATH

    def get_or_clone_repository(self, project_url, project_id, access_token):
        """
        获取或克隆项目仓库

        Returns:
            (success, repo_path, error_message)
        """
        # 1. 检查仓库是否已存在
        # 2. 存在则更新（git fetch）
        # 3. 不存在则克隆（git clone --depth 1）
        # 4. 返回本地路径

    def checkout_merge_request(self, repo_path, mr_iid, source_branch, target_branch):
        """
        切换到 MR 对应的分支

        Returns:
            (success, error_message)
        """
        # 1. git checkout source_branch
        # 2. git pull
        # 3. 返回结果

    def get_commit_range(self, repo_path, target_branch='main'):
        """
        获取当前分支相对于目标分支的提交范围

        Returns:
            (success, commit_range, error_message)
        例如: "abc123..def456"
        """

    def cleanup_old_repositories(self, days=7):
        """
        清理超过指定天数的旧仓库

        Returns:
            (cleaned_count, total_size_freed)
        """
```

#### 关键实现

- **浅克隆优化**：使用 `git clone --depth 1 --no-single-branch` 减少克隆时间
- **认证处理**：构建 `https://oauth2:TOKEN@gitlab.com/user/repo.git` 格式的 URL
- **错误恢复**：如果更新失败，删除并重新克隆
- **超时控制**：Git 命令默认 300 秒超时

### 2. ClaudeCliService (`claude_cli_service.py`)

**职责**：封装 Claude CLI 命令执行

#### 核心方法

```python
class ClaudeCliService:
    def __init__(self, request_id=None):
        self.request_id = request_id
        self.cli_path = settings.CLAUDE_CLI_PATH  # 'claude'
        self.timeout = settings.CLAUDE_CLI_TIMEOUT  # 300s

    def review_code(self, repo_path, custom_prompt=None, commit_range=None):
        """
        使用 Claude CLI 执行代码审查

        Args:
            repo_path: 仓库本地路径
            custom_prompt: 自定义审查提示
            commit_range: Git 提交范围

        Returns:
            (success, result_data, error_message)
        """
        # 1. 构建命令: claude -p "prompt" --output-format json
        # 2. 在 repo_path 目录执行
        # 3. 解析 JSON 输出
        # 4. 返回结果

    def review_with_security_focus(self, repo_path, commit_range=None):
        """执行安全性重点的代码审查"""

    def review_with_performance_focus(self, repo_path, commit_range=None):
        """执行性能优化重点的代码审查"""

    def validate_cli_installation(self):
        """验证 Claude CLI 是否正确安装"""
```

#### 命令执行流程

```python
# 1. 构建命令
command = ['claude', '-p', prompt, '--output-format', 'json']

# 2. 执行
result = subprocess.run(
    command,
    cwd=repo_path,  # 在仓库目录执行
    capture_output=True,
    text=True,
    timeout=300
)

# 3. 解析输出
data = json.loads(result.stdout)
```

### 3. ReviewResultParser (`review_result_parser.py`)

**职责**：解析 Claude CLI 的 JSON 输出

#### 核心方法

```python
class ReviewResultParser:
    def parse(self, claude_output: Dict) -> Dict:
        """
        解析 Claude CLI 的输出结果

        Returns:
            {
                'content': '格式化的审查内容',
                'score': 85,
                'duration_ms': 12345,
                'token_usage': {...},
                'issues': [...],
                'summary': '...',
                'metadata': {...}
            }
        """

    def _extract_issues(self, text: str) -> List[Dict]:
        """提取问题列表"""
        # 识别 🔴 🟠 🟡 🟢 等标记
        # 提取文件名和行号
        # 返回结构化的问题列表

    def _calculate_score(self, text: str, issues: List[Dict]) -> int:
        """计算评分 (0-100)"""
        # 基础分 100
        # 根据问题严重性扣分
        # 查找明确的评分标记

    def _extract_security_issues(self, text: str) -> List[Dict]:
        """提取安全相关问题"""

    def _extract_performance_issues(self, text: str) -> List[Dict]:
        """提取性能相关问题"""
```

#### 解析策略

1. **问题提取**：使用正则表达式匹配 Markdown 标题和严重性标记
2. **评分计算**：
   - 严重问题（🔴）：-20 分
   - 高危问题（🟠）：-10 分
   - 中危问题（🟡）：-5 分
   - 低危问题（🟢）：-2 分
3. **文件定位**：识别 `filename.py:123` 格式的文件引用

### 4. LLMService 集成 (`apps/llm/services.py`)

**修改**：更新 `review_code` 方法以支持 Claude CLI

#### 新签名

```python
def review_code(self, code_context, mr_info=None, repo_path=None, commit_range=None):
    """
    Review code using Claude CLI

    Args:
        code_context: 代码上下文（已弃用，保留向后兼容）
        mr_info: MR 信息字典
        repo_path: 本地仓库路径（必需）
        commit_range: Git 提交范围

    Returns:
        解析后的审查结果字典或错误消息字符串
    """
```

#### 实现逻辑

```python
# 1. 验证 repo_path
if not repo_path:
    return "代码审查失败：未提供仓库路径"

# 2. 初始化服务
cli_service = ClaudeCliService(request_id=self.request_id)

# 3. 验证 CLI 安装
is_valid, error = cli_service.validate_cli_installation()
if not is_valid:
    return f"代码审查失败：{error}"

# 4. 构建提示
custom_prompt = self._build_claude_cli_prompt(mr_info)

# 5. 执行审查
success, result_data, error = cli_service.review_code(
    repo_path=repo_path,
    custom_prompt=custom_prompt,
    commit_range=commit_range
)

# 6. 解析结果
parser = ReviewResultParser(request_id=self.request_id)
parsed_result = parser.parse(result_data)

return parsed_result
```

### 5. Webhook 处理流程更新 (`apps/webhook/views.py`)

**修改**：在 `process_merge_request_review` 函数中集成新流程

#### 更新后的流程

```python
def process_merge_request_review(project_id, merge_request_iid, review_id, payload):
    # 1. 获取 MR 基本信息（保持不变）
    mr_info = {...}

    # 2. 判断模式
    if is_mock_mode:
        # Mock 模式（保持不变）
        ...
    else:
        # === 新增：Claude CLI 模式 ===

        # 3. 初始化仓库管理器
        repo_manager = RepositoryManager(request_id=request_id)

        # 4. 获取项目 URL 和访问令牌
        project_url = project_data.get('git_http_url')
        access_token = gitlab_service.access_token

        # 5. 克隆或更新仓库
        success, repo_path, error = repo_manager.get_or_clone_repository(
            project_url=project_url,
            project_id=project_id,
            access_token=access_token
        )

        # 6. 切换到 MR 分支
        success, error = repo_manager.checkout_merge_request(
            repo_path=repo_path,
            mr_iid=merge_request_iid,
            source_branch=source_branch,
            target_branch=target_branch
        )

        # 7. 获取提交范围
        success, commit_range, error = repo_manager.get_commit_range(
            repo_path=repo_path,
            target_branch=target_branch
        )

        # 8. 调用 LLM 进行代码审查
        llm_service = LLMService(request_id=request_id)
        llm_result = llm_service.review_code(
            code_context=None,
            mr_info=mr_info,
            repo_path=repo_path,
            commit_range=commit_range
        )

        # 9. 检查结果并保存
        if isinstance(llm_result, str):
            # 错误
            review.status = 'failed'
            review.error_message = llm_result
        else:
            # 成功
            review.review_content = llm_result['content']
            review.review_score = llm_result['score']
            review.status = 'completed'

        review.save()

    # 10. 发送通知（保持不变）
    notification_dispatcher.dispatch(...)
```

---

## 配置说明

### Django Settings (`backend/core/settings.py`)

```python
# ===== Claude CLI Code Review Configuration =====

# Repository Management
REPOSITORY_BASE_PATH = os.environ.get(
    'REPOSITORY_BASE_PATH',
    os.path.join(BASE_DIR, 'data', 'repositories')
)

# Claude CLI Configuration
CLAUDE_CLI_PATH = os.environ.get('CLAUDE_CLI_PATH', 'claude')
CLAUDE_CLI_TIMEOUT = int(os.environ.get('CLAUDE_CLI_TIMEOUT', 300))
CLAUDE_CLI_DEFAULT_PROMPT = os.environ.get('CLAUDE_CLI_DEFAULT_PROMPT', """...""")

# Repository Cleanup Configuration
REPOSITORY_CACHE_DAYS = int(os.environ.get('REPOSITORY_CACHE_DAYS', 7))
REPOSITORY_MAX_SIZE_GB = int(os.environ.get('REPOSITORY_MAX_SIZE_GB', 50))

# Ensure repository directory exists
os.makedirs(REPOSITORY_BASE_PATH, exist_ok=True)
```

### 环境变量配置

创建 `.env` 文件：

```bash
# Claude CLI 配置
CLAUDE_CLI_PATH=claude
CLAUDE_CLI_TIMEOUT=300

# 仓库存储配置
REPOSITORY_BASE_PATH=/data/code-review-repositories
REPOSITORY_CACHE_DAYS=7
REPOSITORY_MAX_SIZE_GB=50

# GitLab 配置（必需）
GITLAB_URL=https://gitlab.com
GITLAB_PRIVATE_TOKEN=your-gitlab-access-token

# Mock 模式（开发测试用）
CODE_REVIEW_MOCK_MODE=False
```

### Docker 部署配置

`docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    volumes:
      - ./data/repositories:/app/data/repositories  # 挂载仓库目录
      - ./data/db:/app/data/db  # 挂载数据库
    environment:
      - REPOSITORY_BASE_PATH=/app/data/repositories
      - CLAUDE_CLI_PATH=claude
      - CLAUDE_CLI_TIMEOUT=300
      - GITLAB_URL=${GITLAB_URL}
      - GITLAB_PRIVATE_TOKEN=${GITLAB_PRIVATE_TOKEN}
    depends_on:
      - postgres
```

---

## 使用指南

### 1. 安装 Claude CLI

```bash
# 安装 Claude CLI（假设已有安装方法）
npm install -g @anthropic-ai/claude-cli
# 或
pip install claude-cli

# 验证安装
claude --version
claude --help
```

### 2. 配置 GitLab Access Token

1. 登录 GitLab
2. 进入 **Settings** → **Access Tokens**
3. 创建新 Token，权限选择：
   - `api`
   - `read_repository`
   - `write_repository`
4. 复制 Token 并配置到环境变量

### 3. 启动服务

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 运行迁移
python manage.py migrate

# 启动服务
python manage.py runserver 0.0.0.0:8000
```

### 4. 配置 GitLab Webhook

1. 进入 GitLab 项目 → **Settings** → **Webhooks**
2. 添加 Webhook URL: `https://your-domain.com/api/webhook/gitlab`
3. 选择触发事件：
   - ✅ Merge request events
4. 保存并测试

### 5. 触发代码审查

1. 创建一个新的 Merge Request
2. 系统自动接收 Webhook
3. 后台开始处理：
   - 克隆仓库
   - 切换分支
   - 执行 Claude 审查
   - 解析结果
   - 发送通知

---

## API 参考

### RepositoryManager API

```python
from apps.review.repository_manager import RepositoryManager

# 初始化
manager = RepositoryManager(request_id="req-123")

# 克隆或更新仓库
success, repo_path, error = manager.get_or_clone_repository(
    project_url="https://gitlab.com/user/repo.git",
    project_id=12345,
    access_token="glpat-xxxxx"
)

# 切换分支
success, error = manager.checkout_merge_request(
    repo_path="/data/repositories/project-12345",
    mr_iid=42,
    source_branch="feature/new-feature",
    target_branch="main"
)

# 获取提交范围
success, commit_range, error = manager.get_commit_range(
    repo_path="/data/repositories/project-12345",
    target_branch="main"
)
# commit_range: "abc123..def456"

# 清理旧仓库
count, size = manager.cleanup_old_repositories(days=7)
print(f"清理了 {count} 个仓库，释放 {size/1024/1024:.2f} MB")
```

### ClaudeCliService API

```python
from apps.review.claude_cli_service import ClaudeCliService

# 初始化
service = ClaudeCliService(request_id="req-123")

# 验证 CLI 安装
is_valid, error = service.validate_cli_installation()
if not is_valid:
    print(f"Claude CLI 未安装: {error}")

# 执行代码审查
success, result_data, error = service.review_code(
    repo_path="/data/repositories/project-12345",
    custom_prompt="请从安全角度审查代码",
    commit_range="abc123..def456"
)

# result_data 结构
{
    "type": "result",
    "subtype": "success",
    "result": "审查内容...",
    "duration_ms": 12345,
    "usage": {...}
}

# 安全审查
success, result_data, error = service.review_with_security_focus(
    repo_path="/data/repositories/project-12345"
)

# 性能审查
success, result_data, error = service.review_with_performance_focus(
    repo_path="/data/repositories/project-12345"
)
```

### ReviewResultParser API

```python
from apps.review.review_result_parser import ReviewResultParser

# 初始化
parser = ReviewResultParser(request_id="req-123")

# 解析 Claude 输出
parsed_result = parser.parse(claude_output)

# 返回结构
{
    'content': '完整的审查内容',
    'score': 85,
    'duration_ms': 12345,
    'token_usage': {...},
    'issues': [
        {
            'title': '敏感信息泄露',
            'severity': 'critical',
            'file': 'backend/apps/llm/serializers.py',
            'line': 30,
            'description': '...'
        }
    ],
    'summary': '审查摘要',
    'security_issues': [...],
    'performance_issues': [...],
    'metadata': {
        'score': 85,
        'total_issues': 5,
        'critical_issues': 1,
        'security_issues': 2,
        'performance_issues': 1
    }
}

# 格式化为报告
report_text = parser.format_for_report(parsed_result)
```

---

## 故障排查

### 常见问题

#### 1. Claude CLI 未找到

**错误**：`Claude CLI not found at: claude`

**解决**：
```bash
# 检查 Claude CLI 是否安装
which claude

# 如果未安装，安装 Claude CLI
npm install -g @anthropic-ai/claude-cli

# 或指定完整路径
export CLAUDE_CLI_PATH=/usr/local/bin/claude
```

#### 2. 仓库克隆失败

**错误**：`Failed to clone repository: Authentication failed`

**原因**：GitLab Access Token 无效或权限不足

**解决**：
1. 检查 Token 是否过期
2. 确认 Token 有 `api` 和 `read_repository` 权限
3. 手动测试克隆：
   ```bash
   git clone https://oauth2:YOUR_TOKEN@gitlab.com/user/repo.git
   ```

#### 3. 分支切换失败

**错误**：`Failed to checkout branch feature/xxx`

**原因**：分支不存在或仓库状态异常

**解决**：
```bash
# 进入仓库目录
cd /data/repositories/project-xxx

# 检查分支
git branch -a

# 重置状态
git reset --hard
git clean -fd

# 拉取最新
git fetch --all

# 手动切换
git checkout feature/xxx
```

#### 4. Claude CLI 超时

**错误**：`Claude CLI timeout after 300s`

**原因**：项目过大或网络问题

**解决**：
1. 增加超时时间：
   ```bash
   export CLAUDE_CLI_TIMEOUT=600
   ```
2. 检查网络连接
3. 尝试手动执行命令测试

#### 5. 磁盘空间不足

**错误**：`No space left on device`

**解决**：
```bash
# 检查磁盘空间
df -h

# 清理旧仓库
python manage.py shell
>>> from apps.review.repository_manager import RepositoryManager
>>> manager = RepositoryManager()
>>> count, size = manager.cleanup_old_repositories(days=3)
>>> print(f"清理了 {count} 个仓库，释放 {size/1024/1024:.2f} MB")

# 或手动清理
rm -rf /data/repositories/*
```

### 日志调试

```bash
# 查看日志
tail -f backend/logs/django.log

# 过滤特定请求
grep "req-xxxxx" backend/logs/django.log

# 查看 Git 命令执行
grep "Executing git command" backend/logs/django.log

# 查看 Claude CLI 调用
grep "Claude CLI" backend/logs/django.log
```

---

## 未来优化

### 短期优化（1-2 周）

1. **并发控制**
   - 实现任务队列（Celery）
   - 限制同时克隆的仓库数量
   - 防止磁盘空间耗尽

2. **缓存优化**
   - 缓存审查结果
   - 对相同提交避免重复审查
   - 实现增量审查（只审查变更部分）

3. **错误重试**
   - 克隆失败自动重试
   - Claude CLI 超时重试机制
   - 指数退避策略

### 中期优化（1-2 个月）

1. **性能提升**
   - 使用 Git shallow clone 的 filter 功能
   - 并行处理多个 MR
   - 优化仓库存储结构（按组织/项目分层）

2. **监控和告警**
   - 磁盘空间监控
   - 审查成功率监控
   - 平均审查时间统计
   - Grafana 可视化

3. **配置增强**
   - Web UI 配置 Claude prompt
   - 项目级别的审查配置
   - 自定义审查规则

### 长期优化（3-6 个月）

1. **分布式架构**
   - 多节点部署
   - 仓库分片存储
   - 负载均衡

2. **AI 增强**
   - 结合历史审查数据训练
   - 自动学习项目代码风格
   - 智能问题优先级排序

3. **企业功能**
   - 审查报告模板自定义
   - 合规性检查集成
   - RBAC 权限管理
   - 审计日志

---

## 附录

### A. 文件清单

| 文件路径 | 说明 | 行数 |
|---------|------|------|
| `backend/apps/review/repository_manager.py` | 仓库管理器 | ~350 |
| `backend/apps/review/claude_cli_service.py` | Claude CLI 服务 | ~280 |
| `backend/apps/review/review_result_parser.py` | 结果解析器 | ~320 |
| `backend/apps/llm/services.py` | LLM 服务（已修改） | ~250 |
| `backend/apps/webhook/views.py` | Webhook 处理（已修改） | ~1100 |
| `backend/core/settings.py` | 配置文件（已修改） | ~290 |

### B. 配置参数完整列表

| 参数名 | 类型 | 默认值 | 说明 |
|--------|-----|--------|------|
| `REPOSITORY_BASE_PATH` | str | `{BASE_DIR}/data/repositories` | 仓库存储路径 |
| `CLAUDE_CLI_PATH` | str | `claude` | Claude CLI 命令路径 |
| `CLAUDE_CLI_TIMEOUT` | int | `300` | 命令超时时间（秒） |
| `CLAUDE_CLI_DEFAULT_PROMPT` | str | 见配置 | 默认审查提示 |
| `REPOSITORY_CACHE_DAYS` | int | `7` | 仓库缓存天数 |
| `REPOSITORY_MAX_SIZE_GB` | int | `50` | 最大存储空间（GB） |

### C. 数据库表结构变更

虽然当前实现未修改数据库表结构，但建议未来添加以下字段：

```python
class MergeRequestReview(models.Model):
    # 现有字段...

    # 新增字段（建议）
    repository_path = models.CharField(max_length=500, blank=True)
    claude_cli_version = models.CharField(max_length=50, blank=True)
    claude_duration_ms = models.IntegerField(null=True)
    claude_token_usage = models.JSONField(null=True)
    commit_range = models.CharField(max_length=100, blank=True)
```

### D. 参考链接

- [Claude CLI 文档](https://docs.anthropic.com/claude/cli)
- [GitLab Webhooks](https://docs.gitlab.com/ee/user/project/integrations/webhooks.html)
- [Git Shallow Clone](https://git-scm.com/docs/git-clone#Documentation/git-clone.txt---depthltdepthgt)
- [Django Settings Best Practices](https://docs.djangoproject.com/en/stable/topics/settings/)

---

## 版本历史

| 版本 | 日期 | 修改内容 | 作者 |
|-----|------|---------|------|
| 1.0 | 2025-11-08 | 初始版本，完成核心功能实现 | Claude AI |

---

**文档结束**
