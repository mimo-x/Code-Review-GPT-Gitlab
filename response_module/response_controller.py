import threading

from response_module.response_factory import ResponseFactory


class ReviewResponse:
    def __init__(self, config):
        """
        Initialize the ReviewResponse instance with the specified configuration.
        
        Validates that the provided configuration is a dictionary containing the required
        'type' field. Sets up internal storage for replies, a thread lock for safe concurrent
        access, and a state dictionary for extra response data.
        
        Args:
            config (dict): A configuration dictionary that must include a 'type' field.
        
        Raises:
            Exception: If the configuration is not a dictionary or lacks the 'type' field.
        """
        if not isinstance(config, dict):
            raise Exception('Reply config should be a dict.')
        if 'type' not in config:
            raise Exception('Reply config should contain a type field.')
        self.config = config
        self.replies = []
        self.lock = threading.Lock()
        self.oter_res_state = {}

    def add_reply(self, reply_msg):
        """
        Adds a reply message to the response queue.
        
        Validates the reply message to ensure a 'content' field is present and, if provided, that 'msg_type'
        is a comma-separated string. For messages whose type includes 'SINGLE', the message is sent immediately.
        If absent, defaults for 'msg_type', 'target', 'title', and 'group_id' are assigned before the message
        is appended to the replies list with thread-safety.
        
        Args:
            reply_msg (dict): The reply message dictionary. It must include a 'content' field and may include
                an optional 'msg_type' (as a comma-separated string), 'target', 'title', and 'group_id'.
        
        Raises:
            Exception: If the 'content' field is missing or if 'msg_type' is provided but not a string.
        """
        if 'content' not in reply_msg:
            raise Exception('Reply format error, title and content are required.')
        if 'msg_type' in reply_msg:
            if not isinstance(reply_msg['msg_type'], str):
                raise Exception('Reply format error, msg_type should be a string.')
            reply_msg['msg_type'] = [t.strip() for t in reply_msg['msg_type'].split(',')]
            if 'SINGLE' in reply_msg['msg_type']:
                self.send_single_message(reply_msg)
                return
        else:
            reply_msg['msg_type'] = ['NORMAL']
        if 'target' not in reply_msg:
            reply_msg['target'] = 'all'
        if 'title' not in reply_msg:
            reply_msg['title'] = ''
        if 'group_id' not in reply_msg:
            reply_msg['group_id'] = 0
        with self.lock:  # 加锁
            self.replies.append(reply_msg)

    def send(self):
        """
        Sends all accumulated reply messages.
        
        This method groups reply messages by target and message type before dispatching them. Messages with a "MAIN" type are processed separately after clearing the stored replies in a thread-safe manner. For each target group, it retrieves a sender via ResponseFactory and sends the grouped messages. Returns True if all messages are successfully sent; otherwise, False.
        """
        msg_groups = {}
        main_msg_group = []
        with self.lock:  # 加锁
            # 发送所有消息的逻辑
            for msg in self.replies:
                if 'MAIN' in msg['msg_type']:
                    # msg 加入到 main_msg 中
                    main_msg_group.append(msg)
                    continue
                self.__parse_msg(msg, msg_groups)

            self.replies = []  # 清空已发送的消息
        for main_msg in main_msg_group:
            self.__parse_msg(main_msg, msg_groups)
        ret = True
        for target, msg_group in msg_groups.items():
            reply_target = ResponseFactory.get_message_instance(target, self.config)
            for msg in msg_group:
                ret &= reply_target.send(msg)
        return ret

    def send_single_message(self, reply):
        """
        Sends a single reply message to designated targets immediately.
        
        This function processes a reply message dictionary and dispatches the message to one or more
        targets. It splits the 'target' field by commas, and if the keyword 'all' is present, it
        replaces the targets with all available message targets from the ResponseFactory. Depending
        on the 'msg_type' flag and the presence of a valid 'title', the function may prepend a formatted
        title to the message content. It returns True only if the message is successfully sent to all
        designated targets.
         
        Args:
            reply (dict): A dictionary containing message details. Required keys:
                - 'content': The text content of the message.
                - 'target': A comma-separated string of target identifiers, or 'all' for all targets.
              Optional keys:
                - 'msg_type': A string that can include 'TITLE_IGNORE' or 'MAIN' to control title usage.
                - 'title': A string that, if provided and applicable, is used as the message title.
                
        Returns:
            bool: True if the message was sent successfully to every target; False otherwise.
        """
        targets = [t.strip() for t in reply['target'].split(',')]
        if 'all' in targets:
            targets = ResponseFactory.get_all_message_targets()
        ret = True
        for target in targets:
            reply_target = ResponseFactory.get_message_instance(target, self.config)
            if ('TITLE_IGNORE' in reply['msg_type'] or 'MAIN' in reply['msg_type']
                    or 'title' not in reply or not reply['title']):
                ret &= reply_target.send(reply['content'])
            else:
                title = f"## {reply['title']}\n\n" if 'title' in reply else ''
                ret &= reply_target.send(f"{title}{reply['content']}\n\n")
        return ret

    def __parse_msg(self, msg, msg_groups):
        """
        Parse a message and group it by target and group ID.
        
        The function splits the message's target field into individual targets. If the target is missing or includes "all", all targets are retrieved via ResponseFactory. It then updates the msg_groups dictionary by creating or appending to a list of messages under each target and group identifier. When the message type indicates that the title should be ignored, or if it is marked as MAIN or missing a valid title, the content is inserted at the beginning of the group; otherwise, a Markdown header is prepended to the content before appending.
            
        Args:
            msg (dict): A message dictionary expected to include 'target', 'msg_type', 'group_id',
                        'content', and optionally 'title'.
            msg_groups (dict): A nested dictionary grouping messages by target and group_id, which is
                               updated in place with the parsed message.
        """
        targets = [t.strip() for t in msg['target'].split(',')]
        if 'target' not in msg or 'all' in targets:
            targets = ResponseFactory.get_all_message_targets()
        for target in targets:
            if target not in msg_groups:
                msg_groups[target] = {}
            if msg['group_id'] not in msg_groups[target]:
                msg_groups[target][msg['group_id']] = []
            if ('TITLE_IGNORE' in msg['msg_type'] or 'MAIN' in msg['msg_type']
                    or 'title' not in msg or not msg['title']):
                msg_groups[target][msg['group_id']].insert(0, msg['content'])
            else:
                title = f"## {msg['title']}\n\n" if 'title' in msg else ''
                msg_groups[target][msg['group_id']].append(f"{title}{msg['content']}\n\n")

    def set_state(self, res_type, *args, **kwargs):
        """
        Stores state information for a given response type.
        
        This method records additional state details provided as positional or keyword arguments
        and saves them in an internal dictionary for later use.
        
        Args:
            res_type: Identifier for the response type.
            *args: Optional positional state details.
            **kwargs: Optional keyword state details.
        """
        self.oter_res_state[res_type] = (args, kwargs)

    def send_by_other(self, response_type, *args, **kwargs):
        """
        Sends a response using an alternative sender instance.
        
        Retrieves a sender from the ResponseFactory based on the given response type and the instance
        configuration. If a sender is found and a stored state exists for that type, the state is applied
        to the sender before sending the response with the provided arguments. Raises an Exception if
        no sender instance for the specified response type exists.
        
        Args:
            response_type: Identifier for the alternative response type.
            *args: Positional arguments passed to the sender's send method.
            **kwargs: Keyword arguments passed to the sender's send method.
        
        Returns:
            The result of the sender's send method.
        """
        sender = ResponseFactory.get_other_instance(response_type, self.config)
        if sender is None:
            raise Exception(f'No such type {response_type} in other response.')
        if self.oter_res_state.get(response_type):
            sender.set_state(*self.oter_res_state[response_type])
        return sender.send(*args, **kwargs)

if __name__ == '__main__':
    reply = ReviewResponse({'type': 'merge_request',
                   'project_id': 9885,
                   'merge_request_iid': 18})
    threads = []
    for i in range(10):
        threads.append(threading.Thread(target=reply.add_reply, args=(
            {'title': f'title{i}', 'content': f'content{i}', 'target': 'gitlab, dingtalk', 'priority': i % 3},)))
    threads.append(threading.Thread(target=reply.add_reply, args=(
            {'title': '__IGNORE__', 'content': f'content{i}', 'target': 'gitlab, dingtalk', 'priority': i % 3},)))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    reply.send()