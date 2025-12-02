# 常见问题解答 (FAQ)

本文档收集了 Code Review GPT Gitlab 项目使用过程中的常见问题和解决方案。

## 📦 安装与部署

!!! question "Q1: Docker 容器启动失败怎么办？"

    !!! tip "解决方案"
    
        请按以下步骤排查：
    
        1. **检查 Docker 和 Docker Compose 版本**
           ```bash
           docker --version
           docker compose version
           ```
           确保 Docker 20.10+ 和 Docker Compose v2 已安装。
    
        2. **查看容器日志**
           ```bash
           docker compose logs backend
           docker compose logs frontend
           ```
    
        3. **检查端口占用**
           ```bash
           # 检查端口是否被占用
           lsof -i :3000  # 前端端口
           lsof -i :8000  # 后端端口
           lsof -i :6379  # Redis 端口
           ```
    
        4. **重新构建并启动**
           ```bash
           docker compose down
           docker compose up -d --build
           ```

!!! question "Q2: 如何配置环境变量？"

    !!! info "配置步骤"
    
        项目使用 `.env` 文件管理环境变量：
    
        1. 复制示例文件：
           ```bash
           cp .env.example .env
           ```
    
        2. 编辑 `.env` 文件，配置必要的变量：
           - `VITE_API_BASE_URL`: 前端 API 基础地址
           - `VITE_DEV_PROXY_TARGET`: 开发环境代理目标
           - 其他必要的配置项
    
        3. 重启服务使配置生效：
           ```bash
           docker compose restart
           ```

## 🔧 配置问题

!!! question "Q3: 如何配置 GitLab Webhook？"

    !!! info "配置步骤"
    
        配置步骤如下：
    
        1. **获取 Webhook URL**
           - 格式：`http://your-domain.com/api/webhook/gitlab/`
           - 注意：URL 必须以 `/api/webhook/gitlab/` 结尾
    
        2. **在 GitLab 项目中配置 Webhook**
           - 进入项目设置 → Webhooks
           - 填写 Webhook URL
           - 选择触发事件：`Merge Request events`、`Push events` 等
           - 保存配置
    
        3. **在系统中启用项目审查**
           - 登录系统管理界面
           - 进入项目列表
           - 找到对应项目，启用代码审查功能

## 🚀 使用问题

!!! question "Q4: 代码审查没有自动触发怎么办？"

    !!! warning "排查步骤"
    
        请检查以下几点：
    
        1. **检查项目是否启用审查**
           - 确认项目列表中的 `review_enabled` 状态为启用
           - 确认 `auto_review_on_mr` 选项已开启
    
        2. **检查 Webhook 配置**
           - 确认 GitLab Webhook URL 配置正确
           - 确认 Webhook 事件已正确选择
           - 查看 Webhook 日志，确认请求是否到达
    
        3. **检查 Webhook 事件规则**
           - 确认项目已启用对应的 Webhook 事件规则
           - 查看 `Webhook Logs` 确认事件是否被正确识别
    
        4. **查看系统日志**
           ```bash
           docker compose logs -f backend
           ```

!!! question "Q5: 代码审查结果没有发送通知？"

    !!! tip "排查步骤"
    
        排查步骤：
    
        1. **检查通知渠道配置**
           - 确认通知渠道已创建且状态为激活
           - 确认项目已关联通知渠道
           - 检查通知渠道的配置信息是否正确
    
        2. **检查审查状态**
           - 查看审查记录，确认审查状态为 `completed`
           - 检查 `notification_sent` 字段状态
           - 查看 `notification_result` 字段中的错误信息
    
        3. **测试通知渠道**
           - 在管理后台手动测试通知渠道
           - 检查网络连接和 API 密钥是否有效

!!! question "Q6: 如何查看代码审查历史记录？"

    !!! info "查看方式"
    
        有多种方式查看：
    
        1. **通过前端界面**
           - 登录系统前端界面
           - 进入"审查记录"页面
           - 可以按项目、时间范围等条件筛选
    
        2. **通过管理后台**
           - 访问 `http://localhost:8000/admin/`
           - 进入 `Merge Request Reviews` 菜单
           - 查看所有审查记录
    
        3. **查看详细日志**
           - 进入"日志"页面查看详细的处理日志
           - 可以查看 Webhook 接收、LLM 调用、通知发送等各个环节的日志

## 🔍 故障排除

!!! question "Q7: Webhook 请求被拒绝或返回 403/401？"

    !!! warning "可能的原因"
    
        可能的原因：
    
        1. **检查 Webhook Secret Token**
           - 如果配置了 Secret Token，确保系统端也配置了相同的 Token
    
        2. **检查 GitLab Token 权限**
           - 确认 GitLab Token 有足够的权限访问项目
           - 确认 Token 未过期
    
        3. **检查防火墙和网络**
           - 确认服务器可以访问 GitLab
           - 确认 GitLab 可以访问 Webhook URL
    
        4. **查看请求日志**
           - 在 Webhook Logs 中查看详细的请求头和错误信息

!!! question "Q8: 系统运行缓慢或超时？"

    !!! warning "优化建议"
    
        优化建议：
    
        1. **检查资源使用**
           ```bash
           docker stats
           ```
    
        2. **优化 LLM 调用**
           - 使用更快的模型
           - 减少审查的文件数量
           - 配置合理的超时时间
    
        3. **数据库优化**
           - 定期清理旧的日志记录
           - 为常用查询字段添加索引
    
        4. **增加资源**
           - 增加容器内存限制
           - 使用更强大的服务器

## 📚 其他问题

!!! question "Q9: 如何升级到新版本？"

    !!! tip "升级步骤"
    
        升级步骤：
    
        1. **备份当前数据**
           ```bash
           # 备份数据库和配置
           cp backend/db.sqlite3 backend/db.sqlite3.backup
           cp .env .env.backup
           ```
    
        2. **拉取最新代码**
           ```bash
           git pull origin main
           ```
    
        3. **更新依赖**
           ```bash
           docker compose down
           docker compose build --no-cache
           docker compose up -d
           ```
    
        4. **执行数据库迁移**
           ```bash
           docker compose exec backend python manage.py migrate
           ```

!!! question "Q10: 支持哪些编程语言？"

    !!! info "语言支持说明"
    
        理论上支持所有编程语言，因为：
    
        - 系统使用 LLM 进行代码审查，LLM 本身支持多种编程语言
        - 不依赖特定的语法分析器
        - 审查质量取决于 LLM 模型的能力
    
        !!! tip "建议"
        
            建议：
            - 主流语言（Python、JavaScript、Java、Go 等）审查效果较好
            - 对于特殊语言，可能需要定制 Prompt 以获得更好效果

!!! question "Q11: 如何贡献代码或报告问题？"

    !!! success "欢迎贡献"
    
        欢迎贡献：
    
        1. **报告问题**
           - 在 GitHub Issues 中提交问题
           - 提供详细的错误信息和复现步骤
    
        2. **提交代码**
           - Fork 项目
           - 创建功能分支
           - 提交 Pull Request
    
        3. **联系维护者**
           - Email: mixuxin@163.com
           - 微信: isxuxin

---

!!! tip "💡 提示"
    
    如果以上问题都无法解决您的问题，请：
    
    1. 查看项目 [GitHub Issues](https://github.com/mimo-x/Code-Review-GPT-Gitlab/issues)
    2. 查看详细的系统日志
    3. 联系项目维护者获取帮助
    
    **祝您使用愉快！** 🎉
