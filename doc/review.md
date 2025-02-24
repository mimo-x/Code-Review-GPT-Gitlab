# Review Engine 模块说明文档 📄

## 1. 模块总述 🌟

Review Engine 模块主要功能为接收有关mr的信息，调用所有的handler处理信息，生成回复。它通过集成多种处理器（handlers）来分析和处理代码变更信息，并生成相应的审查结果。该模块具有以下特点：

- **拓展性强**：通过动态导入处理器，用户可以轻松添加新的处理器以满足不同的审查需求。
- **模块化设计**：代码结构清晰，易于维护和扩展。

## 2. 主要架构 📐

以下是该模块的主要架构及文件功能说明：

```plaintext
review_engine/
├── review_engine.py         # ReviewEngine 类的实现，负责处理代码审查的主逻辑
├── abstract_handler.py      # 定义了抽象处理器类 ReviewHandle，所有具体处理器需继承此类
└── handler/
    ├── default_handler.py   # 具体处理器 MainReviewHandle 的实现，包含默认的代码审查逻辑
    └── 更多自定义handler
```

### 文件功能说明：

- **review_engine.py**：实现了 ReviewEngine 类，负责加载处理器并处理代码审查请求。
- **abstract_handler.py**：定义了抽象处理器类 ReviewHandle，所有具体处理器需继承此类并实现 `merge_handle` 方法。
- **handler/default_handler.py**：实现了具体的处理器 MainReviewHandle，包含默认的代码审查逻辑。

## 3. 如何添加新的 Handler 🛠️

添加新的处理器非常简单，只需按照以下步骤操作：

1. **创建新的处理器文件**：
   在 `handler` 目录下创建一个新的 Python 文件，例如 `custom_handler.py`。

   > ❗️请务必在handler目录下添加，否则无法识别

2. **继承 ReviewHandle 类**：
   在新的处理器文件中，创建一个handle类并继承 `ReviewHandle` 类。

3. **实现 `merge_handle` 方法**：

   > 目前项目仅支持对merge请求的审查，针对更多类型的审查已经在快马加鞭地开发中...

   在新类中实现 `merge_handle` 方法，编写具体的代码审查逻辑，相关参数的详细说明见**参数说明**部分：
   
   - [gitlabMergeRequestFetcher](#41-GitlabMergeRequestFetcher)：gitlab merge信息管理类，可以通过调用相关方法获取以下信息：
     - [changes](#411-changes) ：merge变更文件的内容
     - [merge_info](#412-merge_info) ：merge的相关信息
   
   - [gitlabRepoManager](#42-GitlabRepoManager)：gitlab项目仓库等管理类，可以通过该类查找仓库中指定内容
   - [hook_info](#43-hook_info) ：hook请求接收到的信息
   - [reply](#44-reply) ：发送生成review的模块
   - [model](#45-model) ：统一的大模型接口模块
   
   

示例代码：

```python
from review_engine.abstract_handler import ReviewHandle

class CustomReviewHandle(ReviewHandle):
    def merge_handle(self, gitlabMergeRequestFetcher, gitlabRepoManager, hook_info, reply, model):
        # 自定义的代码审查逻辑
        changes = gitlabMergeRequestFetcher.get_changes()
        merge_info = gitlabMergeRequestFetcher.get_info()
        source_branch_name = merge_info['source_branch']
        # 其他逻辑
        pass
```

4. 大功告成，``ReviewEngine``将会自动调用所有handle。

## 4. 参数说明 📊

### 4.1 GitlabMergeRequestFetcher

* **位置**：`gitlab_integration.gitlab_fetcher.GitlabMergeRequestFetcher`
* **主要功能**：获取gitlab中关于MergeRequest的相关信息
* **主要方法**：
  * `def get_changes(force=False)`：获取merge request的change信息。
    * `force` (bool, 可选): 是否强制刷新缓存，默认为 `False`。如果设置为 `True`，即使缓存中已有文件内容，也会重新从 GitLab 获取changes内容。
    * 返回的changes信息具体内容参加[changes](#411-changes)。
  * `get_info(force=False)`：获取merge request的merge_info信息。
    * `force` (bool, 可选): 是否强制刷新缓存，默认为 `False`。如果设置为 `True`，即使缓存中已有文件内容，也会重新从 GitLab 获取merge_info内容。
    * 返回的merge_info信息具体内容参加[merge_info](#412-merge_info)。
  * `get_file_content(file_path, branch_name='main', force=False)`：用于从 GitLab 仓库中获取指定文件的内容。该方法会尝试从缓存中读取文件内容，如果缓存中没有该文件或强制刷新缓存，则会通过 GitLab API 获取文件内容。
    * `file_path` (str): 文件的路径，请直接提供用`/`分割的文件路径。该路径会在内部转换，将路径中的斜杠 `/` 替换为 `%2F`，以符合 URL 编码的要求。
    * `branch_name` (str, 可选): 分支的名称，默认为 `'main'`。该参数用于指定从哪个分支获取文件内容。
    * `force` (bool, 可选): 是否强制刷新缓存，默认为 `False`。如果设置为 `True`，即使缓存中已有文件内容，也会重新从 GitLab 获取文件内容。
    * 返回值：如果请求成功，返回文件的内容（字符串）。如果请求失败，返回 `None`。

#### 4.1.1 Changes

- **获取方式**：`gitlabMergeRequestFetcher.get_changes()`
- **来源**：gitlab api中`projects/{project_id}/merge_requests/{iid}/changes` 中的 `changes` 字段。
- **类型**：字典列表。
- **示例**：
  ```json
  [
    {
      "old_path": "file1.txt",
      "new_path": "file1.txt",
      "a_mode": "100644",
      "b_mode": "100644",
      "diff": "@@ -1,4 +1,4 @@\n-hello\n+hello world\n",
      "new_file": false,
      "renamed_file": false,
      "deleted_file": false
    }
  ]
  ```
- **重点内容**：
  - `old_path` 和 `new_path`：文件路径。
  - `diff`：文件变更的详细内容。

#### 4.1.2 Merge_info

* **获取方式**：gitlabMergeRequestFetcher.get_info()

- **来源**：gitlab api中`projects/{project_id}/merge_requests/{iid}`的所有信息。

- **类型**：字典。

- **参考链接**：https://docs.gitlab.com/ee/api/merge_requests.html#get-single-mr

- **重点示例（完整信息和解释参见参考链接）**：

  ```json
  {
    "id": 155016530,
    "iid": 133,
    "project_id": 15513260,
    "title": "Manual job rules",
    "state": "opened",
    "created_at": "2022-05-13T07:26:38.402Z",
    "updated_at": "2022-05-14T03:38:31.354Z",
    "target_branch": "main",
    "source_branch": "manual-job-rules",
    "author": {
      "username": "marcel.amirault",
      "name": "Marcel Amirault",
      "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/4155490/avatar.png"
    },
    "merge_status": "can_be_merged",
    "web_url": "https://gitlab.com/marcel.amirault/test-project/-/merge_requests/133",
    "head_pipeline": {
      "id": 538317940,
      "status": "failed",
      "web_url": "https://gitlab.com/marcel.amirault/test-project/-/pipelines/538317940"
    }
  }
  ```

- **重点内容**：

  - **id**: 合并请求的唯一标识符。
    - **示例**: `155016530`
    - **解释**: 用于在系统中唯一标识此合并请求。
  - **iid**: 项目内的合并请求编号。
    - **示例**: `133`
    - **解释**: 项目内的合并请求编号，通常用于在项目内引用合并请求。
  - **project_id**: 项目 ID。
    - **示例**: `15513260`
    - **解释**: 合并请求所属项目的唯一标识符。
  - **title**: 合并请求的标题。
    - **示例**: `"Manual job rules"`
    - **解释**: 合并请求的标题，描述了此次合并请求的主要内容。
  - **state**: 合并请求的状态。
    - **示例**: `"opened"`
    - **解释**: 合并请求的当前状态，如 `opened`、`closed`、`merged` 等。
  - **created_at**: 合并请求的创建时间。
  - **updated_at**: 合并请求的更新时间。
  - **target_branch**: 目标分支。
  - **source_branch**: 源分支。
  - **author**: 合并请求的作者信息。
  - **merge_status**: 合并状态。
  - **web_url**: 合并请求的网页 URL。
  - **head_pipeline**: 合并请求的最新流水线信息。

### 4.2 GitlabRepoManager

* **位置**：`gitlab_integration.gitlab_fetcher.GitlabRepoManager`

* **主要功能**：可以通过浅clone的方式获取项目中指定分支的内容，并提供支持正则语法的全文查找功能

* **主要方法**：

  * `get_info()`：用于获取项目的信息。该方法通过 GitLab API 获取项目的详细信息。
    - 返回值：如果请求成功，返回项目的信息（JSON 格式）。如果请求失败，返回 `None`。

  * `shallow_clone(branch_name='main')`：执行仓库的浅克隆操作。浅克隆只会克隆指定分支的最新提交记录。

    - `branch_name` (str, 可选): 要克隆的分支名称，默认为 `'main'`。该参数用于指定要克隆的分支。

    - 该方法会删除目标目录中已有的仓库，并使用构建的认证 URL 执行 `git clone` 命令。如果克隆失败，会记录错误日志。

  * `checkout_branch(branch_name, force=False)`：切换到指定的分支。如果仓库尚未克隆，则会执行浅克隆操作。

    - `branch_name` (str): 要切换到的分支名称。

    - `force` (bool, 可选): 是否强制切换分支，默认为 `False`。如果设置为 `True`，即使当前分支已经是目标分支，也会重新克隆。

    - 该方法会检查是否已经在目标分支上，如果不是或 `force` 为 `True`，则会执行浅克隆。

  * `delete_repo()`：删除现有的仓库目录。
    - 该方法会检查目标目录是否存在，如果存在则删除整个目录及其内容。

  * `find_files_by_keyword(keyword, branch_name='main')`：查找仓库中包含指定关键词的文件列表。

    - `keyword` (str): 要查找的关键词。该关键词会被编译成正则表达式，用于在文件内容中搜索。

    - `branch_name` (str, 可选): 要搜索的分支名称，默认为 `'main'`。该参数用于指定要搜索的分支。

    - 返回值：返回一个包含匹配文件路径的列表。如果文件无法读取（例如编码错误、文件不存在或权限问题），则会跳过该文件。

### 4.3 Hook_info

- **来源**：Webhook 接收到的内容。

- **类型**：字典。

- **参考链接**：https://docs.gitlab.com/ee/user/project/integrations/webhook_events.html#merge-request-events

- **重点示例：**

  ```json
  {
    "object_kind": "merge_request",
    "event_type": "merge_request",
    "user": {
      "username": "root",
      "name": "Administrator",
      "avatar_url": "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40\u0026d=identicon"
    },
    "project": {
      "id": 1,
      "name": "Gitlab Test",
      "web_url": "http://example.com/gitlabhq/gitlab-test",
      "namespace": "GitlabHQ",
      "path_with_namespace": "gitlabhq/gitlab-test",
      "default_branch": "master"
    },
    "object_attributes": {
      "id": 99,
      "iid": 1,
      "target_branch": "master",
      "source_branch": "ms-viewport",
      "title": "MS-Viewport",
      "state": "opened",
      "created_at": "2013-12-03T17:23:34Z",
      "updated_at": "2013-12-03T17:23:34Z",
      "merge_status": "unchecked",
      "url": "http://example.com/diaspora/merge_requests/1"
    },
    "last_commit": {
      "id": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
      "message": "fixed readme",
      "timestamp": "2012-01-03T23:36:29+02:00",
      "url": "http://example.com/awesome_space/awesome_project/commits/da1560886d4f094c3e6c9ef40349f7d38b5d27d7"
    }
  }
  ```

- **重点解释**

  - **object_kind**: 事件类型。
    - **示例**: `"merge_request"`
    - **解释**: **目前只包含这一种类型**。

  - **event_type**: 具体事件类型。
    - **示例**: `"merge_request"`
    - **解释**: 具体的事件类型，同样表示这是一个合并请求事件。

  - **user**: 触发事件的用户信息，包含触发事件的用户的用户名、姓名和头像 URL。
    
  - **project**: 项目信息，包含项目的 ID、名称、网页 URL、命名空间、路径和默认分支。
    
  - **object_attributes**: 合并请求的详细信息，包含合并请求的 ID、内部编号、目标分支、源分支、标题、状态、创建和更新时间、合并状态和网页 URL。
    
  - **last_commit**: 合并请求中最新提交的信息，包含最新提交的 ID、提交信息、时间戳和提交网页 URL。
    

### 4.4 Reply

* **来源**：``reply_module.reply.Reply``的实例化对象
* **类型：** Rpely
* **参考链接：**reply.md
* **使用说明：**
  
  * 重点只会使用**reply.add_reply(config)**方法，将handler生成的信息添加到reply的消息列表，并进行处理和发送。
  
  * **config 参数说明：**详细说明参见reply.md中reply_msg部分：[跳转到 3.2 Reply Message (reply_msg)
  
    * `content`: 每个 `reply_msg` 一定包含该参数，表示消息的实际内容。
    * `title`: 可选参数，表示消息的标题。
    * `msg_type`: 表示消息的类型，默认值为 `NORM`。
    * ``target``：标识发送给哪些平台，默认为``all``
    * `group_id`: 表示消息的分组ID，默认值为 `0`。
    
    ```python
    reply_msg = {
        "content": "This is a message content",
        "title": "Optional Title",
        "msg_type": "NORM",
      	"target": "all",
        "group_id": 0
    }
    ```
    
  * 使用示例：
  
    ```python
    reply.add_reply({
        'title': '__MAIN_REVIEW__',
        'content': (
            f"## 项目名称: **{hook_info['project']['name']}**\n\n"
            f"### 合并请求详情\n"
            f"- **MR URL**: [查看合并请求]({hook_info['object_attributes']['url']})\n"
            f"- **源分支**: `{hook_info['object_attributes']['source_branch']}`\n"
            f"- **目标分支**: `{hook_info['object_attributes']['target_branch']}`\n\n"
            f"### 变更详情\n"
            f"- **修改文件个数**: `{len(changes)}`\n"
            f"- **Code Review 状态**: ✅\n"
        ),
        'target': 'dingtalk, gitlab',
        'msg_type': 'MAIN, SINGLE',
        "group_id": 0
    })
    ```

### 4.5 Model

* **来源**：``large_model``中api类的实例化对象

* **功能：**使开发者无需关心大模型api配置即可调用模型生成review。

* **方法说明：**

  * ``generate_text(msg)``：根据提供的提示词生成回复
  * ``get_respond_content()``：获取生成的回复
  * ``get_respond_tokens()``：获取回复的token数

* **示例：**

  ```python
  try:
      content = filter_diff_content(change['diff'])
      messages = [
          {"role": "system",
           "content": gpt_message
           },
          {"role": "user",
           "content": f"请review这部分代码变更{content}",
           },
      ]
      log.info(f"发送给gpt 内容如下：{messages}")
      model.generate_text(messages)
      response_content = model.get_respond_content().replace('\n\n', '\n')
      return review_note
  except Exception as e:
      log.error(f"GPT error:{e}")
  ```

  
