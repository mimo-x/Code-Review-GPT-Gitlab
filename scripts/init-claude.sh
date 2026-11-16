#!/usr/bin/env bash
#
# init-claude.sh - Claude Code 环境初始化脚本
#
# 功能：
#   1. 检查并安装 Claude CLI（如未安装）
#   2. 验证 CLI 安装和 API 连通性
#   3. 确保项目 CLAUDE.md 存在
#   4. 设置 .env 中的 Claude CLI 配置
#
# 用法：
#   bash scripts/init-claude.sh              # 交互式初始化
#   bash scripts/init-claude.sh --no-prompt  # 非交互式（跳过安装确认）
#   bash scripts/init-claude.sh --docker     # Docker 模式（仅验证）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
NO_PROMPT=false
DOCKER_MODE=false

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-prompt) NO_PROMPT=true; shift ;;
        --docker)    DOCKER_MODE=true; shift ;;
        *)           echo "未知参数: $1"; exit 1 ;;
    esac
done

echo ""
echo "================================================"
echo "  Claude Code 环境初始化"
echo "  Code Review GPT GitLab"
echo "================================================"
echo ""

# ============================================================
# Step 1: 检查操作系统兼容性
# ============================================================
log_info "Step 1/5: 检查操作系统兼容性..."

OS="$(uname -s)"
case "$OS" in
    Linux|Darwin)
        log_ok "操作系统: $OS - 兼容"
        ;;
    *)
        log_error "不支持的操作系统: $OS"
        log_info "Claude CLI 仅支持 macOS 10.15+ 和 Linux x86_64/ARM64"
        exit 1
        ;;
esac

# ============================================================
# Step 2: 检查/安装 Claude CLI
# ============================================================
log_info "Step 2/5: 检查 Claude CLI 安装状态..."

CLAUDE_PATH="${CLAUDE_CLI_PATH:-claude}"

if command -v "$CLAUDE_PATH" &> /dev/null; then
    CLAUDE_BIN="$CLAUDE_PATH"
elif command -v claude &> /dev/null; then
    CLAUDE_BIN="claude"
else
    CLAUDE_BIN=""
fi

if [ -n "$CLAUDE_BIN" ]; then
    CLAUDE_VERSION=$("$CLAUDE_BIN" --version 2>&1 || echo "unknown")
    log_ok "Claude CLI 已安装: $CLAUDE_VERSION (路径: $(command -v "$CLAUDE_BIN"))"
else
    log_warn "未检测到 Claude CLI"

    if [ "$DOCKER_MODE" = true ]; then
        log_warn "Docker 模式下跳过安装，请确保 Dockerfile 已包含安装步骤"
    else
        if [ "$NO_PROMPT" = true ]; then
            INSTALL="y"
        else
            echo ""
            read -r -p "是否现在安装 Claude CLI？(y/N) " INSTALL
        fi

        if [ "${INSTALL:-n}" = "y" ] || [ "${INSTALL:-n}" = "Y" ]; then
            log_info "正在通过官方脚本安装 Claude CLI..."
            log_info "执行: curl -fsSL https://claude.ai/install.sh | bash"

            if curl -fsSL https://claude.ai/install.sh | bash; then
                # 将 ~/.local/bin 添加到 PATH
                export PATH="$HOME/.local/bin:$PATH"

                if command -v claude &> /dev/null; then
                    CLAUDE_BIN="claude"
                    log_ok "Claude CLI 安装成功"
                else
                    log_error "安装完成但未找到 claude 命令，请检查 PATH 设置"
                    log_info "尝试: export PATH=\"\$HOME/.local/bin:\$PATH\""
                    exit 1
                fi
            else
                log_error "Claude CLI 安装失败"
                log_info "请手动安装: curl -fsSL https://claude.ai/install.sh | bash"
                exit 1
            fi
        else
            log_warn "跳过 Claude CLI 安装"
            log_info "如需代码审查功能，请稍后运行: curl -fsSL https://claude.ai/install.sh | bash"
        fi
    fi
fi

# ============================================================
# Step 3: 验证 API 连通性
# ============================================================
log_info "Step 3/5: 验证 API 连通性..."

if [ -n "${CLAUDE_BIN:-}" ]; then
    if [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ] || [ -n "${ANTHROPIC_API_KEY:-}" ]; then
        log_info "检测到 ANTHROPIC 认证凭据，进行连通性测试..."
        echo ""
        TEST_OUTPUT=$("$CLAUDE_BIN" -p "Say 'Claude Code initialization successful'" --output-format json 2>&1 || true)

        if echo "$TEST_OUTPUT" | grep -iq "successful\|initialization"; then
            log_ok "API 连通性测试通过"
        else
            log_warn "API 连通性测试未返回预期结果"
            log_info "响应内容: ${TEST_OUTPUT:0:200}"
            log_info "这可能是因为认证未完成，请确保已设置 ANTHROPIC_AUTH_TOKEN 或 ANTHROPIC_API_KEY"
        fi
    else
        log_warn "未设置 ANTHROPIC_AUTH_TOKEN 或 ANTHROPIC_API_KEY 环境变量"
        log_info "跳过 API 连通性验证"
        echo ""
        log_info "配置方法："
        log_info "  1. 通过 Web 管理界面 → Claude CLI 配置 → 设置认证令牌"
        log_info "  2. 或设置环境变量: export ANTHROPIC_AUTH_TOKEN=your_token"
        log_info "  3. 或通过 .env 文件设置（见 Step 5）"
    fi
else
    log_warn "Claude CLI 不可用，跳过 API 连通性验证"
fi

# ============================================================
# Step 4: 检查 CLAUDE.md
# ============================================================
log_info "Step 4/5: 检查项目 CLAUDE.md..."

if [ -f "$PROJECT_ROOT/CLAUDE.md" ]; then
    CLAUDE_MD_SIZE=$(wc -l < "$PROJECT_ROOT/CLAUDE.md")
    log_ok "CLAUDE.md 已存在 ($CLAUDE_MD_SIZE 行)"
else
    log_warn "CLAUDE.md 不存在"
    log_info "CLAUDE.md 用于指导 Claude Code 了解项目结构和开发约定"
    log_info "项目已有默认的 CLAUDE.md 模板，可通过 git 获取"
fi

# ============================================================
# Step 5: 设置 .env 配置
# ============================================================
log_info "Step 5/5: 设置 .env 环境变量..."

if [ -f "$ENV_FILE" ]; then
    log_info ".env 文件已存在，检查 Claude CLI 相关配置..."

    # 检查 CLAUDE_CLI_PATH
    if grep -q "^CLAUDE_CLI_PATH=" "$ENV_FILE" 2>/dev/null; then
        CURRENT_CLI_PATH=$(grep "^CLAUDE_CLI_PATH=" "$ENV_FILE" | head -1 | cut -d= -f2)
        log_info "CLAUDE_CLI_PATH: ${CURRENT_CLI_PATH:-claude}"
    else
        echo "CLAUDE_CLI_PATH=claude" >> "$ENV_FILE"
        log_ok "已添加 CLAUDE_CLI_PATH=claude 到 .env"
    fi

    # 检查 CLAUDE_CLI_TIMEOUT
    if grep -q "^CLAUDE_CLI_TIMEOUT=" "$ENV_FILE" 2>/dev/null; then
        CURRENT_TIMEOUT=$(grep "^CLAUDE_CLI_TIMEOUT=" "$ENV_FILE" | head -1 | cut -d= -f2)
        log_info "CLAUDE_CLI_TIMEOUT: ${CURRENT_TIMEOUT:-300}"
    else
        echo "CLAUDE_CLI_TIMEOUT=300" >> "$ENV_FILE"
        log_ok "已添加 CLAUDE_CLI_TIMEOUT=300 到 .env"
    fi

else
    log_warn ".env 文件不存在，创建包含 Claude CLI 默认配置的 .env 文件..."
    cat > "$ENV_FILE" << 'EOF'
# Claude CLI 配置
CLAUDE_CLI_PATH=claude
CLAUDE_CLI_TIMEOUT=300

# LLM API 超时（秒）
LLM_API_TIMEOUT=600
EOF
    log_ok ".env 文件已创建，包含 Claude CLI 默认配置"
fi

# ============================================================
# 完成
# ============================================================
echo ""
echo "================================================"
echo "  初始化完成！"
echo "================================================"
echo ""

if [ "${CLAUDE_BIN:-}" != "" ]; then
    log_ok "Claude CLI: 已安装 ($(command -v "$CLAUDE_BIN"))"
else
    log_warn "Claude CLI: 未安装（代码审查功能将不可用）"
fi

log_info ""
log_info "快速开始："
log_info "  1. 启动后端: cd backend && python manage.py runserver 0.0.0.0:8000"
log_info "  2. 启动前端: cd frontend && npm run dev"
log_info "  3. 访问管理面板: http://localhost:3000"
log_info "  4. 在 'Claude CLI 配置' 页面设置认证令牌"
log_info "  5. 在 'LLM 配置' 页面将 provider 设置为 'claude'"
echo ""

exit 0
