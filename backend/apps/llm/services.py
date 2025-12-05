"""
LLM Service for code review using various LLM providers
"""
import os
import logging
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service for interacting with LLM providers
    """

    def __init__(self, request_id=None):
        self.request_id = request_id
        self._load_config()
        self.prompt_template = getattr(settings, 'GPT_MESSAGE',
                                     "请仔细审查以下代码变更，重点关注：\n1. 代码质量和最佳实践\n2. 潜在的bug和安全问题\n3. 性能优化建议\n4. 代码风格和可读性\n\n请提供具体的改进建议。")

    def _load_config(self):
        """
        从数据库加载 LLM 配置，如缺失则抛出 ImproperlyConfigured
        """
        try:
            from .models import LLMConfig
        except ImportError as exc:
            raise ImproperlyConfigured("无法导入 LLMConfig 模型，请确认 apps.llm 已正确安装") from exc

        llm_config = LLMConfig.objects.filter(is_active=True).first()

        if not llm_config:
            raise ImproperlyConfigured("未检测到有效的 LLM 配置，请在后台管理或接口中创建并启用一条 LLM 配置")

        self.provider = llm_config.provider
        self.api_key = llm_config.api_key
        self.api_base = llm_config.api_base
        self.model = llm_config.model
        self.config_source = "database"
        self.is_mock = self.provider == 'mock'

        api_key_status = "已配置" if self.api_key else "未配置"
        logger.info(
            f"[{self.request_id}] LLM配置加载成功 - 提供商:{self.provider}, 模型:{self.model}, API密钥:{api_key_status}"
        )

        if not self.is_mock:
            if not self.api_key:
                logger.warning(f"[{self.request_id}] LLM 配置缺少 API Key，后续请求可能失败")
            self._set_environment_variables()

    def _set_environment_variables(self):
        """
        将数据库配置设置为环境变量，供 LLM 库使用
        """
        if self.is_mock:
            return

        try:
            # 根据不同的提供商设置相应的环境变量
            if self.provider.lower() == 'openai':
                if self.api_key:
                    os.environ['OPENAI_API_KEY'] = self.api_key
                    logger.info(f"[{self.request_id}] 设置 OPENAI_API_KEY 环境变量")
                if self.api_base:
                    os.environ['OPENAI_API_BASE'] = self.api_base
                    logger.info(f"[{self.request_id}] 设置 OPENAI_API_BASE 环境变量")

            elif self.provider.lower() == 'deepseek':
                if self.api_key:
                    os.environ['DEEPSEEK_API_KEY'] = self.api_key
                    logger.info(f"[{self.request_id}] 设置 DEEPSEEK_API_KEY 环境变量")
                if self.api_base:
                    os.environ['DEEPSEEK_API_BASE'] = self.api_base
                    logger.info(f"[{self.request_id}] 设置 DEEPSEEK_API_BASE 环境变量")

            elif self.provider.lower() == 'gemini':
                if self.api_key:
                    os.environ['GOOGLE_API_KEY'] = self.api_key
                    logger.info(f"[{self.request_id}] 设置 GOOGLE_API_KEY 环境变量")

            # 通用配置，适用于所有提供商
            if self.model:
                os.environ['LLM_MODEL'] = self.model
                logger.info(f"[{self.request_id}] 设置 LLM_MODEL 环境变量: {self.model}")

        except Exception as e:
            logger.error(f"[{self.request_id}] 设置环境变量失败: {e}", exc_info=True)

    def review_code(self, code_context, mr_info=None, repo_path=None, commit_range=None, custom_prompt=None):
        """
        Review code using OpenCode CLI

        Args:
            code_context: 代码上下文（已弃用，保留用于向后兼容）
            mr_info: MR 信息字典
            repo_path: 本地仓库路径（使用 OpenCode CLI 时必需）
            commit_range: Git 提交范围
            custom_prompt: 外部传入的自定义 prompt（优先级最高，来自项目配置）

        Returns:
            解析后的审查结果字典或错误消息字符串
        """
        import time
        start_time = time.time()

        logger.info(f"[{self.request_id}] 开始代码审查 - 使用 OpenCode CLI")
        logger.info(f"[{self.request_id}] 仓库路径: {repo_path}")
        logger.info(f"[{self.request_id}] 提交范围: {commit_range}")

        # 检查是否提供了仓库路径
        if not repo_path:
            error_msg = "代码审查失败：未提供仓库路径，OpenCode CLI 需要本地仓库"
            logger.error(f"[{self.request_id}] {error_msg}")
            return error_msg

        try:
            from apps.review.opencode_cli_service import OpenCodeCliService
            from apps.review.review_result_parser import ReviewResultParser

            # 初始化 OpenCode CLI 服务
            cli_service = OpenCodeCliService(request_id=self.request_id)

            # 验证 OpenCode CLI 安装
            is_valid, validation_error = cli_service.validate_cli_installation()
            if not is_valid:
                error_msg = f"代码审查失败：{validation_error}"
                logger.error(f"[{self.request_id}] {error_msg}")
                return error_msg

            # 执行代码审查
            if custom_prompt:
                logger.info(f"[{self.request_id}] 接收到自定义 Prompt，作为 OpenCode CLI 命令的附加参数传入")

            success, result_data, error = cli_service.review_code(
                repo_path=repo_path,
                commit_range=commit_range,
                custom_prompt=custom_prompt
            )

            elapsed_time = time.time() - start_time

            if not success:
                error_msg = f"代码审查失败: {error}"
                logger.error(f"[{self.request_id}] {error_msg}")
                return error_msg

            # 解析审查结果
            parser = ReviewResultParser(request_id=self.request_id)
            parsed_result = parser.parse(result_data)

            logger.info(f"[{self.request_id}] 代码审查完成 - 耗时:{elapsed_time:.2f}秒")
            logger.info(f"[{self.request_id}] 评分:{parsed_result['score']}, 问题数:{len(parsed_result['issues'])}")

            return parsed_result

        except ImportError as e:
            logger.error(f"[{self.request_id}] 导入模块失败: {e}")
            return f"代码审查失败：缺少必要的模块\n错误详情: {str(e)}"
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{self.request_id}] 代码审查异常 - 耗时:{elapsed_time:.2f}秒, 错误:{e}", exc_info=True)
            return f"代码审查失败: {str(e)}"

    def _review_with_openai(self, code_context, start_time):
        """
        Fallback to OpenAI client if UnionLLM is not available
        """
        import time
        try:
            from openai import OpenAI

            prompt = self._build_prompt(code_context)

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base if self.api_base else None
            )

            logger.info(f"[{self.request_id}] 使用OpenAI客户端开始调用API")
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位资深的代码审查专家,擅长发现代码中的问题并提供建设性的改进建议。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            elapsed_time = time.time() - start_time
            review_content = response.choices[0].message.content
            logger.info(f"[{self.request_id}] OpenAI客户端代码审查完成 - 耗时:{elapsed_time:.2f}秒, 响应长度:{len(review_content)}字符")
            return review_content

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{self.request_id}] OpenAI客户端调用失败 - 耗时:{elapsed_time:.2f}秒, 错误:{e}", exc_info=True)
            return f"代码审查失败: {str(e)}"

    def _build_prompt(self, code_context):
        """
        Build the review prompt with code context
        """
        return f"{self.prompt_template}\n\n## 代码变更内容:\n\n{code_context}"
