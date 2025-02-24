# Response 模块中文说明文档



## 1. 代码架构

### 树形图

```
response_module/
├── response_controller.py
├── response_factory.py
├── response_target/
│   ├── msg_response
│		│		├──dingtalk_response.py
│		│		├──gitlab_response.py
│		│		└──更多自定义文字类型回复...
│   └── other_type_response
│		  	└──更多自定义非文字类型回复
└── abstract_response.py
```

### 文件功能简要说明

- **response_controller.py**: 主要负责回复消息的管理和发送逻辑。包括添加回复消息、发送所有消息以及实时发送单条消息。
- **response_factory.py**: 实现了回复目标的工厂模式，用于创建不同类型的回复实例。
- **abstract_response.py**: 定义了一个抽象基类 `AbstractResponse`，所有具体的回复类型都需要继承这个基类并实现其抽象方法,即**开发者需要通过继承此类来实现添加新Response**。
- **response_target/**: 存放具体的回复实现类，例如 `dingtalk_response.py` 和 `gitlab_response.py`，**自定义的回复类可以放于此处**。

## 2. 如何添加自定义的通知方式

>> 🚀 **增强功能**: 添加新的通知方式可以扩展系统的功能，使项目能够支持更多的消息发送平台。例如，除了现有的 Gitlab 和 Dingtalk 外，还可以添加对 Slack、Email 或其他平台的支持。
>>
>> 💡 **Response类型**: 自定义回复类型分为两种，最常用的是文本类型，为提高自定义程度，也支持不太常用的其他类型。

### 步骤详细说明

#### 文本类型Response类（最常用）：

> 文本类型即发送文字内容的回复，比如：邮箱提醒，钉钉提醒，gitlab评论等。

1. **创建新的 Response 类**

    * 在 `response_module/response_target/msg_response` 目录下创建一个新的 Python 文件，例如 `slack_response.py`。
    * 文件中新建一个Response类，例如`SlackResponse`，并实现`AbstractResponseMessage`类，示例如下：

    ```python
    from response_module.abstract_response import AbstractResponseMessage
    
    class SlackResponse(AbstractResponseMessage):
        def __init__(self, config):
            super().__init__(config)
    
        def send(self, message):
            # 这里实现发送消息到 Slack 的逻辑
            print(f"Sending message to Slack: {message}")
            return True
    ```

    * config 主要包含了需要处理的请求的类型（`type`），如 `merge_request`，`push`等，参见[Config参数说明](#31-config)。
    * message 为`String`，内容为要发送的信息。

2. **将新的 Response 类添加到工厂中**

    在 `response_factory.py` 文件中注册新的 Response 类：

    ```python
    from response_module.response_target.slack_response import SlackResponse
    
    ResponseFactory.register_target('slack', SlackResponse)
    ```

    这样，工厂类 `ResponseFactory` 就可以自动创建新的 `SlackResponse` 实例了。

3. **使用自定义类**

   可以在自定义的Handle中使用新定义的类，使用方法参考使用示例。

#### 其他类型Response类（一般用户可忽略）：

> 其他类型不局限发送回复的形式，比如用户需要在自定义handler检测出某严重问题后直接发送给服务器某些指令可以通过该类完成

1. **创建新的 Response 类**

   * 在 `response_module/response_target/other_type_response` 目录下创建一个新的 Python 文件，例如 `server_response.py`。
   * 文件中新建一个Response类，例如`ServerResponse`，并实现`AbstractResponseOther`类，示例如下：

   ```python
   from response_module.abstract_response import AbstractResponseOther
   
   class ServerResponse(AbstractResponseOther):
       def __init__(self, config):
           super().__init__(config)
   
       @abstractmethod
       def set_state(self, *args, **kwargs):
         	# 如果需要，请在调用send()方法前先调用该方法，可以用于配置一些内容
           pass
   
       @abstractmethod
       def send(self, *args, **kwargs):
         	# set_state()后调用该方法，请实现发送逻辑
           pass
   ```

   * config 主要包含了需要处理的请求的类型（`type`），如 `merge_request`，`push`等，参见[Config参数说明](#31-config)。
   * set_state 方法可以传入各种参数，用于配置参数等
   * send 中实现发送逻辑

2. **将新的 Response 类添加到工厂中**

   在 `response_factory.py` 文件中注册新的 Response 类：

   ```python
   from response_module.response_target.slack_response import ServerResponse
   
   ResponseFactory.register_target('server', ServerResponse)
   ```

   这样，工厂类 `ResponseFactory` 就可以自动创建新的 `ServerResponse` 实例了。

3. **使用自定义类**

   可以在自定义的Handle中使用新定义的类，使用方法参考使用示例。

## 3. 参数说明

### 3.1 Config 

#### 3.1.1 功能

`config` 是一个字典，包含了初始化 Response 实例时需要的配置信息。其功能如下：

1. **说明当前 Hook 的类型**: 如 `merge_request`，`push` 等。
2. **包含项目的参数**: 如 `project_id`，`merge_request_iid` 等。

#### 3.1.2 格式

##### 基本格式

- `type`: 每个 `config` 一定包含该参数，根据 `type` 的不同，其他参数会有所不同。
- **目前项目只会有 `merge_request` 一种 `type`，其他事件加急开发中**。

```python
config = {
    "type": "merge_request"
    # 其他参数
}
```

##### merge_request 事件

- `project_id`: 
  - 类型: `int`
  - 说明: 项目的唯一标识符，用于标识具体的项目。

- `merge_request_iid`: 
  - 类型: `int`
  - 说明: 合并请求的唯一标识符，用于标识具体的合并请求。


```python
config = {
    "type": "merge_request",
    "project_id": 95536,  # 项目ID
    "merge_request_iid": 10  # 合并请求IID
}
```

### 3.2 Response Message (response_msg)

#### 3.2.1 功能

`response_msg` 是一个字典，包含了发送消息时所需的信息。其功能如下：

1. **包含消息的实际内容**: 如消息的文本内容、标题等。
2. **定义消息的类型**: 如 `MAIN`，`TITLE_IGNORE`，`SINGLE`，`NORM` 等。
3. **分组消息**: 通过 `group_id` 将相同组的消息一起发送。

#### 3.2.2 格式

##### 基本格式

- `content`: 每个 `response_msg` 一定包含该参数，表示消息的实际内容。
- `title`: 可选参数，表示消息的标题。
- `msg_type`: 表示消息的类型，默认值为 `NORM`。
- ``target``：标识发送给哪些平台，默认为``all``
- `group_id`: 表示消息的分组ID，默认值为 `0`。

```python
response_msg = {
    "content": "This is a message content",
    "title": "Optional Title",
    "msg_type": "NORM",
  	"target": "all",
    "group_id": 0
}
```

##### 字段说明

- `content`:
  - 类型: `str`
  - 说明: 必须包含的字段，表示消息的实际内容。

- `title`:
  - 类型: `str`
  - 说明: 可选字段，表示消息的标题，如果无此字段或内容为空，则等同于``msg_type``为``TITLE_IGNORE``。

- `msg_type`:
  - 类型: `str`
  - 说明: 表示消息的类型, 可以为多个类型，通过逗号``,``分割。默认值为 `NORM`，可选值包括：
    - `MAIN`: 标识主消息，要求唯一，项目自带handle默认使用。
    - `TITLE_IGNORE`: 忽略标题，即只发送内容。
    - `SINGLE`: 直接发送单条消息。
    - `NORMAL`: 正常消息类型，等待所有handle处理完成后拼接成一条消息发送。

- ``target``：
  - 类型：``str``
  - 说明：标识调用哪些Response通知类进行·发送，可以同时选择多个Response，通过逗号``,``分割。默认值为 `all`，可选值包括：
    - ``all``：发送给所有在``response_factory.py``中注册过的Response通知类。
    - ``gitlab``：发送给gitlab平台，即在merge界面发送comment
    - ``dingtalk``：配置好钉钉机器人后，可以通过机器人发送到钉钉
    - ``自定义``：可以参考上文自定义Response并在``response_factory.py``中注册，然后可以使用自定义的通知类。
- `group_id`:
  - 类型: `int`
  - 说明: 表示消息的分组ID。相同 `group_id` 的消息会一起发送。默认值为 `0`。
- 

##### 示例

```python
response_msg = {
    "content": "This is the main content of the message.",
    "title": "Important Update",
    "msg_type": "MAIN, SINGLE",
  	"target": "dingtalk, gitlab",
    "group_id": 1
}
```

在上述示例中，`response_msg` 包含了一个主要类型的消息，带有标题，并且属于组 `1`。

## 4. 其他说明

### 示例代码

以下是一个简单的使用示例：

```python
from response_module.response_controller import ReviewResponse

# 配置字典
config = {
    'type': 'merge_request',
    'project_id': 9885,
    'merge_request_iid': 18
}

# 创建 Response 实例
response = ReviewResponse(config)

# 添加文本类型回复
response.add_response({
    "target": "slack",
    "content": "This is a test message",
    "title": "Test Title",
    "msg_type": "NORM",
    "group_id": 0
})

# 发送所有消息
success = response.send()
print(f"Messages sent successfully: {success}")

# 发送其他类型回复
response.set_state("server", "param1", "param2", {"key1": "xxx"}) # 设置Server类状态
response.send_by_other("server", "param1", "param2", {"key1": "xxx"}) # 发送回复

```

通过以上步骤和示例代码，您可以轻松地在项目中添加和使用新的回复类型。

