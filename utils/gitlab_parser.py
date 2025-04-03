import re
from config.config import CONTEXT_LINES_NUM


def filter_diff_content(diff_content):
    # 过滤掉以 - 开头的行和 @@ 开头的行
    filtered_content = re.sub(r'(^-.*\n)|(^@@.*\n)', '', diff_content, flags=re.MULTILINE)
    # 处理代码，去掉以 + 开头的行的第一个字符
    processed_code = '\n'.join([line[1:] if line.startswith('+') else line for line in filtered_content.split('\n')])
    return processed_code


def extract_diffs(diff_content):
    """提取多个diff转成diff数组"""

    # 使用正则表达式来匹配diff数据块
    diff_pattern = re.compile(r'@@ -\d+,\d+ \+\d+,\d+ @@.*?(?=\n@@|\Z)', re.DOTALL)
    diffs = diff_pattern.findall(diff_content)
    return diffs

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

def extract_comment_end_line(diff_content):
    line_range = []

    for line in diff_content.split('\n'):
        if line.startswith('@@'):
            # 提取新的行号
            match = re.match(r'@@ -(\d+)(,\d+)? \+(\d+)(,\d+)? @@', line)
            if match:
                old_line_start = int(match.group(1))
                new_line_start = int(match.group(3))

                # 计算结束行号
                if match.group(2):
                    # 去除逗号并转成int获取行数
                    old_line_count = int(match.group(2)[1:])
                    old_line_end = old_line_start + old_line_count - 1
                else:
                    old_line_end = old_line_start

                if match.group(4):
                    # 去除逗号并转成int获取行数
                    new_line_count = int(match.group(4)[1:])
                    new_line_end = new_line_start + new_line_count - 1
                else:
                    new_line_end = new_line_start

                line_range.append(old_line_end)
                line_range.append(new_line_end)

    return line_range


def get_context_boundaries(diff_range, source_code_length, context_lines_num=CONTEXT_LINES_NUM):
    """计算上下文的行号边界"""
    if not diff_range or len(diff_range) < 2:
        return None, None, None, None

    # 计算上文边界
    front_lines_end = max(diff_range[0] - 1, 1) if diff_range[0] > 1 else None
    front_lines_start = max(diff_range[0] - context_lines_num, 1) if diff_range[0] > 1 else None
    
    # 计算下文边界
    back_lines_start = min(diff_range[1] + 1, source_code_length) if diff_range[1] < source_code_length else None
    back_lines_end = min(diff_range[1] + context_lines_num, source_code_length) if diff_range[1] < source_code_length else None
    
    return front_lines_start, front_lines_end, back_lines_start, back_lines_end

def add_context_to_diff(diff_content, source_code=None, context_lines_num=CONTEXT_LINES_NUM):
    """在diff内容前后添加上下文代码"""

    # 过滤diff内容
    filtered_diff = filter_diff_content(diff_content)

    # 获取同一 diff_content 多处 diff 行号范围和 diff过滤内容
    diff_ranges = []
    filtered_contents = []
    diffs = extract_diffs(diff_content)
    for diff in diffs:
        # 获取单个diff的行号范围
        diff_ranges.append(extract_diff_line_range(diff))
        # 获取单个diff的内容
        filtered_contents.append(filter_diff_content(diff))

    diff_with_contexts = ""

    if source_code and diff_ranges:
        code_lines = source_code.splitlines()
        source_code_length = len(code_lines)



        for filtered_content, diff_range in zip(filtered_contents, diff_ranges):
            front_lines = ""
            back_lines = ""
            diff_with_context = ""
            front_start, front_end, back_start, back_end = get_context_boundaries(
                diff_range, source_code_length, context_lines_num)

            if front_start is not None and front_end is not None and front_end >= front_start:
                for line in range(front_start, front_end + 1):
                    front_lines +=  code_lines[line - 1] + '\n'
                diff_with_context += f"修改代码块前代码：\n{front_lines}\n"

            diff_with_context += f"修改代码块：\n{filtered_content}\n"

            if back_start is not None and back_end is not None and back_end >= back_start:
                for line in range(back_start, back_end + 1):
                    back_lines +=  code_lines[line - 1] + '\n'
                diff_with_context += f"修改代码块后代码：\n{back_lines}\n"


            diff_with_contexts += diff_with_context + '\n'

    return diff_with_contexts if diff_with_contexts else filtered_diff


def get_comment_request_json(comment, change, old_line, new_line, diff_refs):
    """生成 inline comment 请求Json格式"""

    # old 或者 new 无修改将 对应行号置为 None
    old_line = old_line if old_line > 0 else None
    new_line = new_line if new_line > 0 else None
    note = {
        "body": f"{comment}",
        "position": {
            "base_sha": diff_refs['base_sha'],
            "start_sha": diff_refs['start_sha'],
            "head_sha": diff_refs['head_sha'],
            "position_type": "text",
            "old_path": change['old_path'],
            "old_line": old_line,
            "new_path": change['new_path'],
            "new_line": new_line,
            # "line_range": {
            #     "start": {
            #         # "line_code": "ca08fab203917f02c97701e43c3cf87140bb6643_31_30",
            #         "type": "new",
            #         "new_line": 30,
            #     },
            #     "end": {
            #         # "line_code": "ca08fab203917f02c97701e43c3cf87140bb6643_33_35",
            #         "type": "new",
            #         "new_line": 35,
            #     },
            #
            # }
        }
    }

    return note

if __name__ == "__main__":
    diff_content = "@@ -3 +1,5 @@\n-hello\n+hello world\n"
    print(extract_diff_line_range(diff_content))