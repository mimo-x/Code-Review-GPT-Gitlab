import re


def filter_diff_content(diff_content):
    # 过滤掉以 - 开头的行和 @@ 开头的行
    filtered_content = re.sub(r'(^-.*\n)|(^@@.*\n)', '', diff_content, flags=re.MULTILINE)
    # 处理代码，去掉以 + 开头的行的第一个字符
    processed_code = '\n'.join([line[1:] if line.startswith('+') else line for line in filtered_content.split('\n')])
    return processed_code