"""
Review Result Parser for Claude CLI Output
Parses Claude CLI JSON output and formats it for storage and display
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ReviewResultParser:
    """
    Parser for Claude CLI review results
    """

    def __init__(self, request_id=None):
        self.request_id = request_id

    def parse(self, claude_output: Dict) -> Dict:
        """
        解析 Claude CLI 的输出结果

        Args:
            claude_output: Claude CLI 返回的 JSON 数据

        Returns:
            解析后的审查数据字典:
            {
                'content': '格式化的审查内容',
                'score': 85,  # 0-100
                'duration_ms': 12345,
                'token_usage': {...},
                'issues': [...],
                'summary': '...',
                'metadata': {...}
            }
        """
        try:
            result_text = claude_output.get('result', '')

            # 提取基本信息
            parsed_data = {
                'content': result_text,
                'raw_result': claude_output,
                'duration_ms': claude_output.get('duration_ms', 0),
                'duration_api_ms': claude_output.get('duration_api_ms', 0),
                'num_turns': claude_output.get('num_turns', 0),
                'token_usage': claude_output.get('usage', {}),
                'model_usage': claude_output.get('modelUsage', {}),
                'total_cost_usd': claude_output.get('total_cost_usd', 0.0),
            }

            # 解析审查内容
            parsed_data['issues'] = self._extract_issues(result_text)
            parsed_data['score'] = self._calculate_score(result_text, parsed_data['issues'])
            parsed_data['summary'] = self._extract_summary(result_text)
            parsed_data['security_issues'] = self._extract_security_issues(result_text)
            parsed_data['performance_issues'] = self._extract_performance_issues(result_text)

            # 构建元数据
            parsed_data['metadata'] = {
                'score': parsed_data['score'],
                'total_issues': len(parsed_data['issues']),
                'critical_issues': len([i for i in parsed_data['issues'] if i.get('severity') == 'critical']),
                'security_issues': len(parsed_data['security_issues']),
                'performance_issues': len(parsed_data['performance_issues']),
                'duration_seconds': parsed_data['duration_ms'] / 1000,
                'total_cost': parsed_data['total_cost_usd'],
            }

            logger.info(f"[{self.request_id}] Parsed review result: {parsed_data['metadata']}")

            return parsed_data

        except Exception as e:
            logger.error(f"[{self.request_id}] Error parsing Claude output: {e}", exc_info=True)
            # 返回基本结构以避免崩溃
            return {
                'content': claude_output.get('result', 'Error parsing result'),
                'score': 0,
                'issues': [],
                'summary': 'Error parsing review result',
                'metadata': {},
                'raw_result': claude_output,
            }

    def _extract_issues(self, text: str) -> List[Dict]:
        """
        从审查文本中提取问题列表

        Args:
            text: 审查文本

        Returns:
            问题列表
        """
        issues = []

        try:
            # 查找标记为严重、高危、中危等级别的问题
            severity_patterns = [
                (r'🔴\s*严重|严重安全风险|Critical', 'critical'),
                (r'🟠\s*高危|High', 'high'),
                (r'🟡\s*中危|次要|Medium', 'medium'),
                (r'🟢\s*低危|建议|Low', 'low'),
            ]

            # 按行分析
            lines = text.split('\n')
            current_issue = None
            current_severity = 'medium'

            for line in lines:
                stripped = line.strip()

                # 检测严重性级别
                for pattern, severity in severity_patterns:
                    if re.search(pattern, stripped, re.IGNORECASE):
                        current_severity = severity
                        break

                # 检测问题标题（通常以 **数字.** 或 ### 开头）
                title_match = re.match(r'^[#*]+\s*\d+[\.、]\s*(.+)|^\*\*(\d+)\.\s*(.+)\*\*', stripped)
                if title_match:
                    if current_issue:
                        issues.append(current_issue)

                    title = title_match.group(1) or title_match.group(3) or stripped
                    current_issue = {
                        'title': title.strip('*# '),
                        'description': '',
                        'severity': current_severity,
                        'file': None,
                        'line': None,
                    }

                # 提取文件和行号信息
                file_match = re.search(r'`?([a-zA-Z0-9_/\.\-]+\.py|\.js|\.vue|\.java|\.go):(\d+)', stripped)
                if file_match and current_issue:
                    current_issue['file'] = file_match.group(1)
                    current_issue['line'] = int(file_match.group(2))

                # 添加描述行
                if current_issue and stripped and not title_match:
                    if current_issue['description']:
                        current_issue['description'] += '\n'
                    current_issue['description'] += stripped

            # 添加最后一个问题
            if current_issue:
                issues.append(current_issue)

            logger.info(f"[{self.request_id}] Extracted {len(issues)} issues from review")

        except Exception as e:
            logger.error(f"[{self.request_id}] Error extracting issues: {e}")

        return issues

    def _calculate_score(self, text: str, issues: List[Dict]) -> int:
        """
        根据审查内容计算评分

        Args:
            text: 审查文本
            issues: 问题列表

        Returns:
            评分 (0-100)
        """
        try:
            # 基础分数
            score = 100

            # 根据问题数量和严重程度扣分
            for issue in issues:
                severity = issue.get('severity', 'medium')
                if severity == 'critical':
                    score -= 20
                elif severity == 'high':
                    score -= 10
                elif severity == 'medium':
                    score -= 5
                elif severity == 'low':
                    score -= 2

            # 查找明确的评分标记
            score_match = re.search(r'评分[：:]\s*(\d+)', text)
            if score_match:
                explicit_score = int(score_match.group(1))
                # 使用显式评分和计算评分的平均值
                score = (score + explicit_score) // 2

            # 确保分数在 0-100 范围内
            score = max(0, min(100, score))

            logger.info(f"[{self.request_id}] Calculated review score: {score}")

            return score

        except Exception as e:
            logger.error(f"[{self.request_id}] Error calculating score: {e}")
            return 70  # 默认分数

    def _extract_summary(self, text: str) -> str:
        """
        提取审查摘要

        Args:
            text: 审查文本

        Returns:
            摘要文本
        """
        try:
            # 查找摘要部分
            summary_patterns = [
                r'##\s*摘要\s*\n(.+?)(?=\n##|\n\n|\Z)',
                r'##\s*Summary\s*\n(.+?)(?=\n##|\n\n|\Z)',
                r'##\s*总结\s*\n(.+?)(?=\n##|\n\n|\Z)',
            ]

            for pattern in summary_patterns:
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    summary = match.group(1).strip()
                    logger.info(f"[{self.request_id}] Extracted summary: {summary[:100]}...")
                    return summary

            # 如果没有找到摘要部分，使用前200字符
            lines = text.split('\n')
            summary_lines = []
            for line in lines[:10]:  # 取前10行
                if line.strip() and not line.strip().startswith('#'):
                    summary_lines.append(line.strip())
                if len(' '.join(summary_lines)) > 200:
                    break

            summary = ' '.join(summary_lines)[:200]
            return summary if summary else '代码审查已完成'

        except Exception as e:
            logger.error(f"[{self.request_id}] Error extracting summary: {e}")
            return '代码审查已完成'

    def _extract_security_issues(self, text: str) -> List[Dict]:
        """
        提取安全相关问题

        Args:
            text: 审查文本

        Returns:
            安全问题列表
        """
        security_issues = []

        try:
            # 安全关键词
            security_keywords = [
                'SQL注入', 'XSS', 'CSRF', '命令注入', '路径遍历',
                'API Key', 'Token', '密码', 'Secret', '硬编码',
                '认证', '授权', '权限', '加密', '明文'
            ]

            lines = text.split('\n')
            for i, line in enumerate(lines):
                for keyword in security_keywords:
                    if keyword.lower() in line.lower():
                        # 获取上下文
                        context_start = max(0, i - 1)
                        context_end = min(len(lines), i + 2)
                        context = '\n'.join(lines[context_start:context_end])

                        security_issues.append({
                            'keyword': keyword,
                            'line_number': i + 1,
                            'context': context,
                        })
                        break  # 每行只记录一次

            logger.info(f"[{self.request_id}] Found {len(security_issues)} security-related mentions")

        except Exception as e:
            logger.error(f"[{self.request_id}] Error extracting security issues: {e}")

        return security_issues

    def _extract_performance_issues(self, text: str) -> List[Dict]:
        """
        提取性能相关问题

        Args:
            text: 审查文本

        Returns:
            性能问题列表
        """
        performance_issues = []

        try:
            # 性能关键词
            performance_keywords = [
                'N+1', '性能', '优化', '缓存', '索引',
                '复杂度', '内存泄漏', '并发', '异步'
            ]

            lines = text.split('\n')
            for i, line in enumerate(lines):
                for keyword in performance_keywords:
                    if keyword.lower() in line.lower():
                        # 获取上下文
                        context_start = max(0, i - 1)
                        context_end = min(len(lines), i + 2)
                        context = '\n'.join(lines[context_start:context_end])

                        performance_issues.append({
                            'keyword': keyword,
                            'line_number': i + 1,
                            'context': context,
                        })
                        break

            logger.info(f"[{self.request_id}] Found {len(performance_issues)} performance-related mentions")

        except Exception as e:
            logger.error(f"[{self.request_id}] Error extracting performance issues: {e}")

        return performance_issues

    def format_for_report(self, parsed_data: Dict) -> str:
        """
        将解析后的数据格式化为报告文本

        Args:
            parsed_data: 解析后的数据

        Returns:
            格式化的报告文本
        """
        try:
            report_parts = []

            # 标题和摘要
            report_parts.append(f"# 代码审查报告\n")
            report_parts.append(f"**评分**: {parsed_data['score']}/100\n")
            report_parts.append(f"**问题总数**: {len(parsed_data['issues'])}\n")
            report_parts.append(f"**审查耗时**: {parsed_data['duration_ms'] / 1000:.2f}秒\n")
            report_parts.append(f"\n## 摘要\n{parsed_data['summary']}\n")

            # 主要问题
            if parsed_data['issues']:
                report_parts.append(f"\n## 发现的问题\n")
                for i, issue in enumerate(parsed_data['issues'], 1):
                    severity_emoji = {
                        'critical': '🔴',
                        'high': '🟠',
                        'medium': '🟡',
                        'low': '🟢'
                    }.get(issue['severity'], '⚪')

                    report_parts.append(f"\n### {severity_emoji} {i}. {issue['title']}\n")

                    if issue.get('file'):
                        report_parts.append(f"**文件**: `{issue['file']}`")
                        if issue.get('line'):
                            report_parts.append(f" (行 {issue['line']})")
                        report_parts.append('\n')

                    if issue.get('description'):
                        report_parts.append(f"{issue['description']}\n")

            # 原始内容
            report_parts.append(f"\n## 详细分析\n{parsed_data['content']}\n")

            # 元数据
            report_parts.append(f"\n---\n")
            report_parts.append(f"*审查由 Claude AI 完成，耗时 {parsed_data['duration_ms']}ms*\n")

            return '\n'.join(report_parts)

        except Exception as e:
            logger.error(f"[{self.request_id}] Error formatting report: {e}")
            return parsed_data.get('content', 'Error formatting report')
