import threading

from response_module.response_factory import ResponseFactory


class ReviewResponse:
    def __init__(self, config):
        """
        初始化 Reply 实例
        Args:
            config (dict): 配置字典，包含初始化所需的配置信息
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
        添加回复消息
        Args:
            reply_msg (dict): 回复消息字典，必须包含 'content' 字段
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
        实时发送单条消息
        Args:
            reply (dict): 单条回复消息字典，必须包含 'content' 字段
        Returns:
            bool: 表示发送是否成功
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
        实时发送单条消息

        Args:
            reply (dict): 单条回复消息字典，必须包含 'content' 字段
        Returns:
            bool: 表示发送是否成功
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
        self.oter_res_state[res_type] = (args, kwargs)

    def send_by_other(self, response_type, *args, **kwargs):
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