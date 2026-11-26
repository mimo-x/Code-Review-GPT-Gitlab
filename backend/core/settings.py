"""
Django settings for Code Review GPT project.
"""

import os
from pathlib import Path

# 加载环境变量
try:
    from dotenv import load_dotenv
    # .env 文件在项目根目录（backend 的上一级）
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"✓ 已加载环境变量文件: {env_path}")
    else:
        print(f"⚠ 环境变量文件不存在: {env_path}")
except ImportError:
    print("⚠ python-dotenv 未安装，将使用系统环境变量")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    # Custom apps
    'apps.webhook',
    'apps.review',
    'apps.response',
    'apps.llm',
    'apps.api_auth',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database - SQLite configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# 测试环境使用内存 SQLite，避免影响开发数据库
import sys
if 'test' in sys.argv or 'pytest' in sys.modules:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = False

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.api_auth.authentication.CookieTokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
    # 时区设置：使用本地时区（Asia/Shanghai）而不是 UTC
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',  # 返回格式化的本地时间
}

# CORS settings
# 接口使用 Cookie 登录态，只允许白名单中的源携带凭据跨域访问
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://localhost:5175,http://127.0.0.1:5175',
    ).split(',')
    if origin.strip()
]

# 更详细的CORS配置
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-gitlab-token'
]
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT'
]

# 设置CORS预检请求缓存时间
CORS_PREFLIGHT_MAX_AGE = 86400

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# GitLab Configuration is managed via database (GitLabConfig)

# DingTalk Configuration (configured via NotificationChannel)
DINGDING_BOT_WEBHOOK = None
DINGDING_SECRET = None

# Code Review Settings
EXCLUDE_FILE_TYPES = os.environ.get('EXCLUDE_FILE_TYPES', '.sql,.dump,.lock,.log,.tmp,.bak').split(',')
IGNORE_FILE_TYPES = os.environ.get('IGNORE_FILE_TYPES', '.md,.txt,.json,.xml,.yml,.yaml').split(',')

# LLM Configuration (configured via LLMConfig)
LLM_PROVIDER = None
LLM_API_KEY = None
LLM_API_BASE = None
LLM_MODEL = None

# Review Prompt Template
GPT_MESSAGE = """
你是一位资深代码审查专家。请审查这个 Merge Request 的代码变更，只报告真实、具体、值得处理的问题，重点关注：
1. 逻辑错误、边界条件和异常处理
2. 安全问题：鉴权、注入、敏感信息泄露
3. 数据一致性和并发问题
4. 性能问题
5. 明显影响可维护性的设计问题
"""

# 审查结果的输出语言：zh-CN 或 en
REVIEW_OUTPUT_LANGUAGE = os.environ.get('REVIEW_OUTPUT_LANGUAGE', 'zh-CN')
# 单个 MR 最多保留的行内评论数，超出的问题只出现在总结里
def _env_int(name, default):
    value = os.environ.get(name, '').strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f'环境变量 {name} 必须是整数，当前值为 {value!r}') from None


REVIEW_MAX_INLINE_COMMENTS = _env_int('REVIEW_MAX_INLINE_COMMENTS', 20)

# Create logs directory if it doesn't exist
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

# Mock Mode Configuration（请通过 LLMConfig 设置 provider='mock' 来启用）
CODE_REVIEW_MOCK_MODE = False

# ===== Claude CLI Code Review Configuration =====
# Repository Management
REPOSITORY_BASE_PATH = os.environ.get(
    'REPOSITORY_BASE_PATH',
    os.path.join(BASE_DIR, 'data', 'repositories')
)

# Claude CLI Configuration
CLAUDE_CLI_PATH = os.environ.get('CLAUDE_CLI_PATH', 'claude')
CLAUDE_CLI_TIMEOUT = int(os.environ.get('CLAUDE_CLI_TIMEOUT', 300))  # seconds

# Repository Cleanup Configuration
REPOSITORY_CACHE_DAYS = int(os.environ.get('REPOSITORY_CACHE_DAYS', 7))  # 保留天数
REPOSITORY_MAX_SIZE_GB = int(os.environ.get('REPOSITORY_MAX_SIZE_GB', 50))  # 最大存储空间

# Ensure repository directory exists
os.makedirs(REPOSITORY_BASE_PATH, exist_ok=True)

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = None
EMAIL_PORT = None
EMAIL_HOST_USER = None
EMAIL_HOST_PASSWORD = None
EMAIL_USE_TLS = True
EMAIL_FROM = None

# Slack Configuration
SLACK_WEBHOOK_URL = None

# Feishu Configuration
FEISHU_WEBHOOK_URL = None
FEISHU_SECRET = None

# WeChat Work Configuration
WECHAT_WORK_WEBHOOK_URL = None
