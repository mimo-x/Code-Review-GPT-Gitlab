import re
from config.config import CONTEXT_LINES_NUM


def filter_diff_content(diff_content):
    # 过滤掉以 - 开头的行和 @@ 开头的行
    filtered_content = re.sub(r'(^-.*\n)|(^@@.*\n)', '', diff_content, flags=re.MULTILINE)
    # 处理代码，去掉以 + 开头的行的第一个字符
    processed_code = '\n'.join([line[1:] if line.startswith('+') else line for line in filtered_content.split('\n')])
    return processed_code

def extract_diff_line_range(diff_content):
    """提取diff中的开始和结束行号"""
    line_range = []
    
    for line in diff_content.split('\n'):
        if line.startswith('@@'):
            # 提取新的行号
            match = re.match(r'@@ -\d+(,\d+)? \+(\d+)(,\d+)? @@', line)
            if match:
                start_line = int(match.group(2))
                line_range.append(start_line)
                
                # 计算结束行号
                if match.group(3):
                    # 去除逗号并转成int获取行数
                    line_count = int(match.group(3)[1:])
                    end_line = start_line + line_count - 1
                else:
                    end_line = start_line
                    
                line_range.append(end_line)

    return line_range

def get_context_boundaries(diff_range, source_code_length, context_lines_num=CONTEXT_LINES_NUM):
    """计算上下文的行号边界"""
    if not diff_range or len(diff_range) < 2:
        return None, None, None, None
        
    # 计算上文边界
    front_lines_end = max(diff_range[0] - 1, 1)
    front_lines_start = max(diff_range[0] - context_lines_num, 1)
    
    # 计算下文边界
    back_lines_start = min(diff_range[1] + 1, source_code_length)
    back_lines_end = min(diff_range[1] + context_lines_num, source_code_length)
    
    return front_lines_start, front_lines_end, back_lines_start, back_lines_end

def add_context_to_diff(diff_content, source_code=None, context_lines_num=CONTEXT_LINES_NUM):
    """在diff内容前后添加上下文代码"""
    # 获取diff的行号范围
    diff_range = extract_diff_line_range(diff_content)
    # 过滤diff内容
    filtered_diff = filter_diff_content(diff_content)
    front_lines = ""
    back_lines = ""
    diff_with_context = ""

    if source_code and diff_range:
        code_lines = source_code.splitlines()
        source_code_length = len(code_lines)
        
        front_start, front_end, back_start, back_end = get_context_boundaries(
            diff_range, source_code_length, context_lines_num)
        
        
        if front_start is not None and front_end is not None and front_end >= front_start:
            for line in range(front_start, front_end + 1):
                front_lines += code_lines[line - 1] + '\n'
            diff_with_context += f"修改代码块前代码：\n{front_lines}\n"
        
        diff_with_context += f"修改代码块：\n{filtered_diff}\n"
        
        if back_start is not None and back_end is not None and back_end >= back_start:
            for line in range(back_start, back_end + 1):
                back_lines += code_lines[line - 1] + '\n'
            diff_with_context += f"修改代码块后代码：\n{back_lines}\n"

    return diff_with_context if diff_with_context else filtered_diff


if __name__ == "__main__":
    diff_content = "@@ -3 +1,5 @@\n-hello\n+hello world\n"
    print(extract_diff_line_range(diff_content))