import re
from django.conf import settings


def parse_diff_content(diff_content):
    """
    Parse diff content and extract code changes
    """
    filtered_content = re.sub(r'(^-.*\n)|(^@@.*\n)', '', diff_content, flags=re.MULTILINE)
    processed_code = '\n'.join([line[1:] if line.startswith('+') else line for line in filtered_content.split('\n')])
    return processed_code


def extract_diffs(diff_content):
    """
    Extract multiple diff blocks from diff content
    """
    diff_pattern = re.compile(r'@@ -\d+,\d+ \+\d+,\d+ @@.*?(?=\n@@|\Z)', re.DOTALL)
    diffs = diff_pattern.findall(diff_content)
    return diffs


def extract_diff_line_range(diff_content):
    """
    Extract line range from diff content
    """
    line_range = []

    for line in diff_content.split('\n'):
        if line.startswith('@@'):
            match = re.match(r'@@ -\d+(,\d+)? \+(\d+)(,\d+)? @@', line)
            if match:
                start_line = int(match.group(2))
                line_range.append(start_line)

                if match.group(3):
                    line_count = int(match.group(3)[1:])
                    end_line = start_line + line_count - 1
                else:
                    end_line = start_line

                line_range.append(end_line)

    return line_range
