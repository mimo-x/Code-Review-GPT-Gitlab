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

if __name__ == "__main__":
    diff_content = "@@ -3 +1,5 @@\n-hello\n+hello world\n"
    print(filter_diff_new_line(diff_content))