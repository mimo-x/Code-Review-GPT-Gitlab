import re


def filter_diff_content(diff_content):
    # 过滤掉以 - 开头的行和 @@ 开头的行
    filtered_content = re.sub(r'(^-.*\n)|(^@@.*\n)', '', diff_content, flags=re.MULTILINE)
    # 处理代码，去掉以 + 开头的行的第一个字符
    processed_code = '\n'.join([line[1:] if line.startswith('+') else line for line in filtered_content.split('\n')])
    return processed_code

def filter_diff_new_line(diff_content):
    # 获取diff中的行号
    line_numbers = []
    current_line_num = None

    for line in diff_content.split('\n'):
        if line.startswith('@@'):
            # 提取新的行号
            match = re.match(r'@@ -\d+(,\d+)? \+(\d+)(,\d+)? @@', line)
            if match:
                current_line_num = int(match.group(2))
                line_numbers.append(current_line_num)
                if match.group(3):
                    # 去除match.group(3)的,然后转成int
                    current_line_num += int(match.group(3)[1:]) - 1
                line_numbers.append(current_line_num)

    return line_numbers

def filter_diff_add_context(diff_content, source_code = None, context_lines_num = 5):

    line_numbers = filter_diff_new_line(diff_content)
    diff_content = filter_diff_content(diff_content)
    code_lines = source_code.split('\n')
    front_lines = ""
    back_lines = ""

    # 获取 diff 部分 截取上下文边界
    front_lines_end = max(line_numbers[0] - 1, 1)
    front_lines_start = max(line_numbers[0] - context_lines_num, 1)

    back_lines_start = min(line_numbers[1] + 1, len(code_lines))
    back_lines_end = min(line_numbers[1] + context_lines_num, len(code_lines))

    # 获取上下文内容
    if front_lines_end > front_lines_start:
        for line in range(front_lines_start, front_lines_end + 1):
            front_lines += code_lines[line - 1] + '\n'

    if back_lines_end > back_lines_start:
        for line in range(back_lines_start, back_lines_end + 1):
            back_lines += code_lines[line - 1] + '\n'

    diff_with_context = front_lines + diff_content + back_lines

    return diff_with_context


if __name__ == "__main__":
    diff_content = "@@ -3 +1,5 @@\n-hello\n+hello world\n"
    print(filter_diff_new_line(diff_content))