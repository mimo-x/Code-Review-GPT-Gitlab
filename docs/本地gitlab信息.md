# 本地 GitLab 信息

## GitLab 服务器信息
- **GitLab 地址**: http://localhost:8080/
- **GitLab 版本**: 18.5 Community Edition
- **管理员账号**: Administrator (@root)
- **管理员密码**: glft-9r6bBVPtx1m3NdCsXKHu

## Access Token 信息
- **Token**: glpat-1oPhecNKB2pmfbJn--zLtG86MQp1OjEH.01.0w1773gog
- **Token 类型**: Personal Access Token
- **权限范围**: API access

## 已创建项目

### code-review-test
- **项目 ID**: 1
- **项目名称**: code-review-test
- **项目描述**: Code review test project
- **完整路径**: root/code-review-test
- **可见性**: private (私有)
- **默认分支**: main
- **创建时间**: 2025-11-04T23:56:35.812+08:00

#### 项目 URL
- **Web URL**: http://localhost:8080/root/code-review-test
- **Git HTTP URL**: http://localhost:8080/root/code-review-test.git
- **Git SSH URL**: ssh://git@localhost:2222/root/code-review-test.git
- **README URL**: http://localhost:8080/root/code-review-test/-/blob/main/README.md

#### 项目功能
- Issues: 已启用
- Merge Requests: 已启用
- Wiki: 已启用
- CI/CD Jobs: 已启用
- Snippets: 已启用
- Container Registry: 已启用
- Packages: 已启用
- Service Desk: 未启用

#### API ��接
- **Self**: http://localhost:8080/api/v4/projects/1
- **Issues**: http://localhost:8080/api/v4/projects/1/issues
- **Merge Requests**: http://localhost:8080/api/v4/projects/1/merge_requests
- **Branches**: http://localhost:8080/api/v4/projects/1/repository/branches
- **Labels**: http://localhost:8080/api/v4/projects/1/labels
- **Events**: http://localhost:8080/api/v4/projects/1/events
- **Members**: http://localhost:8080/api/v4/projects/1/members

## API 使用示例

### 创建项目
```bash
curl -X POST "http://localhost:8080/api/v4/projects" \
  -H "PRIVATE-TOKEN: glpat-1oPhecNKB2pmfbJn--zLtG86MQp1OjEH.01.0w1773gog" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "项目名称",
    "description": "项目描述",
    "visibility": "private",
    "initialize_with_readme": true
  }'
```

### 获取项目信息
```bash
curl -X GET "http://localhost:8080/api/v4/projects/1" \
  -H "PRIVATE-TOKEN: glpat-1oPhecNKB2pmfbJn--zLtG86MQp1OjEH.01.0w1773gog"
```

### 列出所有项目
```bash
curl -X GET "http://localhost:8080/api/v4/projects" \
  -H "PRIVATE-TOKEN: glpat-1oPhecNKB2pmfbJn--zLtG86MQp1OjEH.01.0w1773gog"
```

## 注意事项
- 这是本地开发环境的 GitLab 实例
- Access Token 具有完整的 API 访问权限,请妥善保管
- SSH 端口为 2222,而非默认的 22
