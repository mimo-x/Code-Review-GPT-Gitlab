"""
LLM Service for code review using various LLM providers
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service for interacting with LLM providers
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.api_key = settings.LLM_API_KEY
        self.api_base = settings.LLM_API_BASE
        self.model = settings.LLM_MODEL
        self.prompt_template = settings.GPT_MESSAGE

    def review_code(self, code_context):
        """
        Review code using LLM
        """
        try:
            # Import UnionLLM for multiple provider support
            from unionllm import UnionLLM

            # Build the prompt
            prompt = self._build_prompt(code_context)

            # Initialize LLM client
            client_config = {
                "api_key": self.api_key,
                "model": self.model,
                "provider": self.provider,
            }

            if self.api_base:
                client_config["api_base"] = self.api_base

            logger.info(f"Using LLM provider: {self.provider}, model: {self.model}")

            # Call LLM
            llm = UnionLLM(**client_config)

            messages = [
                {"role": "system", "content": "你是一位资深的代码审查专家,擅长发现代码中的问题并提供建设性的改进建议。"},
                {"role": "user", "content": prompt}
            ]

            response = llm.chat(messages=messages)

            if response and hasattr(response, 'choices') and len(response.choices) > 0:
                review_content = response.choices[0].message.content
                logger.info("Code review completed successfully")
                return review_content
            else:
                logger.error("Invalid response from LLM")
                return "代码审查失败：LLM返回无效响应"

        except ImportError:
            logger.error("UnionLLM not installed. Trying with OpenAI client...")
            return self._review_with_openai(code_context)
        except Exception as e:
            logger.error(f"Error during code review: {e}", exc_info=True)
            return f"代码审查失败: {str(e)}"

    def _review_with_openai(self, code_context):
        """
        Fallback to OpenAI client if UnionLLM is not available
        """
        try:
            from openai import OpenAI

            prompt = self._build_prompt(code_context)

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base if self.api_base else None
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位资深的代码审查专家,擅长发现代码中的问题并提供建设性的改进建议。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            review_content = response.choices[0].message.content
            logger.info("Code review completed with OpenAI client")
            return review_content

        except Exception as e:
            logger.error(f"Error with OpenAI client: {e}", exc_info=True)
            return f"代码审查失败: {str(e)}"

    def _build_prompt(self, code_context):
        """
        Build the review prompt with code context
        """
        return f"{self.prompt_template}\n\n## 代码变更内容:\n\n{code_context}"
