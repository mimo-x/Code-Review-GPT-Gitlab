"""
报告生成器 - 负责生成Mock报告和封装真实LLM输出
"""
import logging
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    报告生成器，支持Mock模式和真实LLM输出封装
    """

    def __init__(self, request_id=None):
        self.request_id = request_id

    def generate_mock(self, mr_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成Mock报告
        """
        try:
            project_name = mr_info.get('project_name', '未知项目')
            mr_title = mr_info.get('title', '未知MR')
            mr_author = mr_info.get('author', '未知作者')
            file_count = mr_info.get('file_count', 0)
            changes_count = mr_info.get('changes_count', 0)

            mock_content = f"""# 🤖 代码审查报告 (Mock模式)

## 📋 基本信息
- **项目**: {project_name}
- **MR**: {mr_title}
- **作者**: {mr_author}
- **审查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **文件数量**: {file_count}
- **变更行数**: {changes_count}

## ✅ 审查结果
- **总体评分**: ⭐⭐⭐⭐ (良好)
- **主要问题**: 0个严重问题，2个建议改进
- **代码质量**: 符合规范，可读性良好

## 🔍 详细分析

### 代码质量
- **结构设计**: ✅ 良好
- **命名规范**: ✅ 符合规范
- **注释质量**: ✅ 适当
- **错误处理**: ⚠️ 建议加强

### 安全性
- **输入验证**: ✅ 已实现
- **权限控制**: ✅ 合理
- **数据加密**: ✅ 必要时使用

### 性能
- **算法效率**: ✅ 可接受
- **数据库查询**: ⚠️ 建议优化
- **缓存使用**: ➖ 无相关需求

## 💡 改进建议
1. **错误处理**: 建议在关键函数中添加更详细的异常处理
2. **代码注释**: 可以为复杂逻辑添加更多说明性注释
3. **单元测试**: 建议增加新功能的单元测试覆盖

## 🎯 总结
这是一个质量良好的代码提交，符合团队编码规范。建议在上述几个方面进行小幅优化后可以合并。

---
*此报告由Mock模式生成，仅供参考*
"""

            report_data = {
                'content': mock_content,
                'metadata': {
                    'is_mock': True,
                    'generated_at': datetime.now().isoformat(),
                    'project_name': project_name,
                    'mr_title': mr_title,
                    'file_count': file_count,
                    'changes_count': changes_count,
                    'score': 4.0,
                    'issues_found': 2,
                    'categories': {
                        'code_quality': 'good',
                        'security': 'good',
                        'performance': 'acceptable'
                    }
                }
            }

            logger.info(f"[{self.request_id}] Mock报告生成完成 - 文件数:{file_count}, 评分:4.0")
            return report_data

        except Exception as e:
            logger.error(f"[{self.request_id}] Mock报告生成失败: {e}", exc_info=True)
            return self._generate_error_report("Mock报告生成失败", str(e))

    def generate(self, llm_text: str, mr_info: Dict[str, Any], llm_model: str) -> Dict[str, Any]:
        """
        封装真实LLM输出为报告格式
        """
        try:
            project_name = mr_info.get('project_name', '未知项目')
            mr_title = mr_info.get('title', '未知MR')
            mr_author = mr_info.get('author', '未知作者')
            file_count = mr_info.get('file_count', 0)
            changes_count = mr_info.get('changes_count', 0)

            # 尝试从LLM输出中提取评分
            score = self._extract_score(llm_text)

            # 尝试统计问题数量
            issues_count = self._count_issues(llm_text)

            # 添加元数据头部
            formatted_content = f"""# 🤖 AI代码审查报告

## 📋 基本信息
- **项目**: {project_name}
- **MR**: {mr_title}
- **作者**: {mr_author}
- **审查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **AI模型**: {llm_model}
- **文件数量**: {file_count}
- **变更行数**: {changes_count}

---

{llm_text}

---

*此报告由AI模型 {llm_model} 生成*
"""

            report_data = {
                'content': formatted_content,
                'metadata': {
                    'is_mock': False,
                    'generated_at': datetime.now().isoformat(),
                    'llm_model': llm_model,
                    'project_name': project_name,
                    'mr_title': mr_title,
                    'file_count': file_count,
                    'changes_count': changes_count,
                    'score': score,
                    'issues_found': issues_count,
                    'original_length': len(llm_text)
                }
            }

            logger.info(f"[{self.request_id}] 真实报告生成完成 - 模型:{llm_model}, 文件数:{file_count}, 评分:{score}, 问题数:{issues_count}")
            return report_data

        except Exception as e:
            logger.error(f"[{self.request_id}] 真实报告生成失败: {e}", exc_info=True)
            return self._generate_error_report("报告生成失败", str(e))

    def _extract_score(self, text: str) -> float:
        """
        尝试从LLM输出中提取评分
        """
        try:
            # 查找各种评分模式
            score_patterns = [
                r'评分[：:]\s*(\d+(?:\.\d+)?)/?10?',
                r'得分[：:]\s*(\d+(?:\.\d+)?)/?10?',
                r'★+\s*(\d+(?:\.\d+)?)',
                r'⭐+\s*(\d+(?:\.\d+)?)',
                r'(\d+)分',
                r'等级[：:]\s*[A-D]',
            ]

            for pattern in score_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    score = float(matches[0])
                    # 标准化到0-10分制
                    if score <= 5:
                        score = score * 2
                    return min(score, 10.0)

            # 如果没有找到明确的评分，根据内容进行估算
            positive_words = ['好', '优秀', '良好', '通过', '符合', '正确', '合理']
            negative_words = ['问题', '错误', '不', '需要', '建议', '注意', '风险']

            positive_count = sum(1 for word in positive_words if word in text)
            negative_count = sum(1 for word in negative_words if word in text)

            if positive_count > negative_count:
                return 7.0
            elif negative_count > positive_count:
                return 5.0
            else:
                return 6.0

        except Exception:
            return 6.0  # 默认中等评分

    def _count_issues(self, text: str) -> int:
        """
        统计问题数量
        """
        try:
            issue_patterns = [
                r'问题\d+',
                r'第\d+个问题',
                r'风险\d+',
                r'注意\d+',
                r'建议\d+',
            ]

            total_issues = 0
            for pattern in issue_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                total_issues += len(matches)

            # 如果没有明确的问题编号，通过关键词估算
            if total_issues == 0:
                issue_keywords = ['问题', '错误', '风险', '注意', '建议', '改进', '修复']
                total_issues = sum(1 for keyword in issue_keywords if keyword in text)

            return min(total_issues, 20)  # 限制最大值

        except Exception:
            return 0

    def _generate_error_report(self, error_type: str, error_message: str) -> Dict[str, Any]:
        """
        生成错误报告
        """
        error_content = f"""# ❌ 代码审查报告生成失败

## 错误信息
- **错误类型**: {error_type}
- **错误详情**: {error_message}
- **发生时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 建议
请检查系统配置和日志，联系管理员处理此问题。

---
*报告生成失败，请稍后重试*
"""

        return {
            'content': error_content,
            'metadata': {
                'is_mock': False,
                'is_error': True,
                'generated_at': datetime.now().isoformat(),
                'error_type': error_type,
                'error_message': error_message
            }
        }