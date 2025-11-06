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
        从数据库加载LLM配置，设置为环境变量，如果找不到活跃配置则回退到环境变量
        """
        try:
            from .models import LLMConfig
            llm_config = LLMConfig.objects.filter(is_active=True).first()

            if llm_config:
                self.provider = llm_config.provider
                self.api_key = llm_config.api_key
                self.api_base = llm_config.api_base
                self.model = llm_config.model
                self.config_source = "database"
                api_key_status = "已配置" if self.api_key else "未配置"
                logger.info(f"[{self.request_id}] LLM配置加载成功 - 来源:数据库, 提供商:{self.provider}, 模型:{self.model}, API密钥:{api_key_status}")

                # 将数据库配置设置为环境变量
                self._set_environment_variables()
            else:
                # 回退到环境变量
                self.provider = getattr(settings, 'LLM_PROVIDER', 'openai')
                self.api_key = getattr(settings, 'LLM_API_KEY', '')
                self.api_base = getattr(settings, 'LLM_API_BASE', '')
                self.model = getattr(settings, 'LLM_MODEL', 'gpt-4')
                self.config_source = "environment"
                api_key_status = "已配置" if self.api_key else "未配置"
                logger.info(f"[{self.request_id}] LLM配置加载成功 - 来源:环境变量, 提供商:{self.provider}, 模型:{self.model}, API密钥:{api_key_status}")

        except ImportError:
            logger.warning(f"[{self.request_id}] 无法导入LLMConfig模型，使用环境变量配置")
            self.provider = getattr(settings, 'LLM_PROVIDER', 'openai')
            self.api_key = getattr(settings, 'LLM_API_KEY', '')
            self.api_base = getattr(settings, 'LLM_API_BASE', '')
            self.model = getattr(settings, 'LLM_MODEL', 'gpt-4')
            self.config_source = "environment"
        except Exception as e:
            logger.error(f"[{self.request_id}] LLM配置加载失败: {e}", exc_info=True)
            # 使用环境变量作为最后回退
            self.provider = getattr(settings, 'LLM_PROVIDER', 'openai')
            self.api_key = getattr(settings, 'LLM_API_KEY', '')
            self.api_base = getattr(settings, 'LLM_API_BASE', '')
            self.model = getattr(settings, 'LLM_MODEL', 'gpt-4')
            self.config_source = "environment"

    def _set_environment_variables(self):
        """
        将数据库配置设置为环境变量，供 LLM 库使用
        """
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

            elif self.provider.lower() == 'claude':
                if self.api_key:
                    os.environ['ANTHROPIC_API_KEY'] = self.api_key
                    logger.info(f"[{self.request_id}] 设置 ANTHROPIC_API_KEY 环境变量")

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

    def review_code(self, code_context, mr_info=None):
        """
        Review code using LLM
        """
        import time
        start_time = time.time()

        logger.info(f"[{self.request_id}] 开始代码审查 - 提供商:{self.provider}, 模型:{self.model}")
        
        # Validate API key
        if not self.api_key:
            error_msg = f"API密钥未配置，请检查配置（配置来源:{self.config_source}）"
            logger.error(f"[{self.request_id}] {error_msg}")
            return f"代码审查失败: {error_msg}"
        
        logger.info(f"[{self.request_id}] API密钥状态: {'已配置' if self.api_key else '未配置'} (长度:{len(self.api_key) if self.api_key else 0})")

        try:
            # Import litellm for multiple provider support
            import litellm

            # Build the prompt
            prompt = self._build_prompt(code_context)
            logger.debug(f"[{self.request_id}] Prompt长度: {len(prompt)} 字符")

            # 记录环境变量状态（不显示敏感信息）
            env_status = []
            if self.provider.lower() == 'openai':
                env_status.append(f"OPENAI_API_KEY={'已设置' if os.environ.get('OPENAI_API_KEY') else '未设置'}")
                if os.environ.get('OPENAI_API_BASE'):
                    env_status.append(f"OPENAI_API_BASE={os.environ.get('OPENAI_API_BASE')}")
            elif self.provider.lower() == 'deepseek':
                env_status.append(f"DEEPSEEK_API_KEY={'已设置' if os.environ.get('DEEPSEEK_API_KEY') else '未设置'}")
            elif self.provider.lower() == 'claude':
                env_status.append(f"ANTHROPIC_API_KEY={'已设置' if os.environ.get('ANTHROPIC_API_KEY') else '未设置'}")
            elif self.provider.lower() == 'gemini':
                env_status.append(f"GOOGLE_API_KEY={'已设置' if os.environ.get('GOOGLE_API_KEY') else '未设置'}")

            logger.info(f"[{self.request_id}] 使用环境变量初始化LLM客户端 - 提供商:{self.provider}, 模型:{self.model}, 环境变量:{', '.join(env_status)}")

            messages = [
                {"role": "system", "content": "你是一位资深的代码审查专家,擅长发现代码中的问题并提供建设性的改进建议。"},
                {"role": "user", "content": prompt}
            ]

            logger.info(f"[{self.request_id}] 开始调用LLM API")
            # 使用 litellm 进行调用
            response = litellm.completion(
                model=self.model,
                messages=messages,
                timeout=60
            )

            elapsed_time = time.time() - start_time

            if response and hasattr(response, 'choices') and len(response.choices) > 0:
                review_content = response.choices[0].message.content
                logger.info(f"[{self.request_id}] 代码审查完成 - 耗时:{elapsed_time:.2f}秒, 响应长度:{len(review_content)}字符")
                return review_content
            else:
                logger.error(f"[{self.request_id}] LLM返回无效响应 - 耗时:{elapsed_time:.2f}秒")
                return "代码审查失败：LLM返回无效响应"

        except ImportError:
            logger.error(f"[{self.request_id}] LiteLLM未安装，请安装: pip install litellm")
            return "代码审查失败：LiteLLM库未安装，请安装 pip install litellm"
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{self.request_id}] 代码审查异常 - 耗时:{elapsed_time:.2f}秒, 错误:{e}", exc_info=True)

            # 提供更详细的错误信息
            error_msg = str(e)
            if "AuthenticationError" in error_msg or "api_key" in error_msg.lower():
                logger.error(f"[{self.request_id}] 认证错误，请检查API密钥配置")
                return "代码审查失败：API密钥认证失败，请检查配置"
            elif "timeout" in error_msg.lower():
                logger.error(f"[{self.request_id}] 请求超时")
                return "代码审查失败：请求超时"
            else:
                return f"代码审查失败: {error_msg}"

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
