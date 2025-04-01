# MR summary中用到的 prompt


# LLM summary 模型预设
REVIEW_SUMMARY_SETTING = """Your purpose is to act as a highly experienced
software engineer and provide a thorough review of the code hunks
and suggest code snippets to improve key areas such as:
  - Logic
  - Security
  - Performance
  - Data races
  - Consistency
  - Error handling
  - Maintainability
  - Modularity
  - Complexity
  - Optimization
  - Best practices: DRY, SOLID, KISS

Do not comment on minor code style issues, missing
comments/documentation. Identify and resolve significant
concerns to improve overall code quality while deliberately
disregarding minor issues.
           """


# 单个文件diff review
FILE_DIFF_REVIEW_PROMPT = """## Diff
\`\`\`diff
$file_diff
\`\`\`

## Instructions

I would like you to succinctly summarize the diff within 100 words.
If applicable, your summary should include a note about alterations
to the signatures of exported functions, global data structures and
variables, and any changes that might affect the external interface or
behavior of the code.

    """


# 分批对单文件review结果进行总结
BATCH_SUMMARY_PROMPT = """Provided below are changesets in this merge request. Changesets 
are in chronlogical order and new changesets are appended to the
end of the list. The format consists of filename(s) and the summary 
of changes for those files. There is a separator between each changeset.
Your task is to deduplicate and group together files with
related/similar changes into a single changeset. Respond with the updated 
changesets using the same format as the input. 


$raw_summary
            """


# Comment展示内容
FINAL_SUMMARY_PROMPT = """ Provide your final response in markdown with the following content:

- **总结**: A high-level summary of the overall change instead of
  specific files within 80 words.
- **文件变更**: A markdown table of files and their summaries. Group files
  with similar changes together into a single row to save space. Note that the files in the table do not repeat. The file name is required to be `filename`.
      
Avoid additional commentary as this summary will be added as a comment on the Gitlab merge request. Use the titles "总结" and "文件变更" and they must be H1.
                   """


# Comment展示内容格式控制
SUMMARY_OUTPUT_PROMPT = """Here is the summary of changes you have generated for files:

 \`\`\`
$summaries_content
 \`\`\`

     要求总结用中文回答，尽可能全面且精炼，表格中每一组总结字数不超过50字，请按照上面的规则和下面的格式输出结果，返回格式如下,其中 "{{xxx}}"表示占位符：
# 总结
{{总结内容}}
# 文件变更
| 文件 | 修改摘要 |
|---------|-------------|
| {{`filename1`<br>}} {{`filename2`<br>}} | {{摘要1}} |
| {{`filename3`<br>}} {{`filename4`<br>}}  | {{摘要2}} |

"""




