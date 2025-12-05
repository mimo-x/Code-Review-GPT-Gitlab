"""
Django settings for Code Review GPT project.
"""

import os
from pathlib import Path

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
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
    # 时区设置：使用本地时区（Asia/Shanghai）而不是 UTC
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',  # 返回格式化的本地时间
}

# CORS settings
# 开发环境允许所有源，生产环境需要配置具体的允许源
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:5173,http://localhost:5175,http://127.0.0.1:5175').split(',') if not DEBUG else []

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
EXCLUDE_FILE_TYPES = os.environ.get('EXCLUDE_FILE_TYPES', '.py,.java,.class,.vue,.go,.c,.cpp').split(',')
IGNORE_FILE_TYPES = os.environ.get('IGNORE_FILE_TYPES', 'mod.go').split(',')

# LLM Configuration (configured via LLMConfig)
LLM_PROVIDER = None
LLM_API_KEY = None
LLM_API_BASE = None
LLM_MODEL = None

# Review Prompt Template
GPT_MESSAGE = """
你是一位资深编程专家,gitlab的分支代码变更将以git diff 字符串的形式提供,请你帮忙review本段代码。然后你review内容的返回内容必须严格遵守下面的格式,包括标题内容。模板中的变量内容解释:
变量5为: 代码中的优点。变量1:给review打分,分数区间为0~100分。变量2:code review发现的问题点。变量3:具体的修改建议。变量4:是你给出的修改后的代码。
必须要求:1. 以精炼的语言、严厉的语气指出存在的问题。2. 你的反馈内容必须使用严谨的markdown格式 3. 不要携带变量内容解释信息。4. 有清晰的标题结构。有清晰的标题结构。有清晰的标题结构。
返回格式严格如下:

### 😀代码评分:{变量1}

#### ✅代码优点:
{变量5}

#### 🤔问题点:
{变量2}

#### 🎯修改建议:
{变量3}

#### 💻修改后的代码:
```python
{变量4}
```
"""

# Create logs directory if it doesn't exist
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

# Mock Mode Configuration（请通过 LLMConfig 设置 provider='mock' 来启用）
CODE_REVIEW_MOCK_MODE = False

# ===== OpenCode CLI Code Review Configuration =====
# Repository Management
REPOSITORY_BASE_PATH = os.environ.get(
    'REPOSITORY_BASE_PATH',
    os.path.join(BASE_DIR, 'data', 'repositories')
)

# OpenCode CLI Configuration
OPENCODE_CLI_PATH = os.environ.get('OPENCODE_CLI_PATH', 'opencode')
OPENCODE_CLI_TIMEOUT = int(os.environ.get('OPENCODE_CLI_TIMEOUT', 300))  # seconds

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
