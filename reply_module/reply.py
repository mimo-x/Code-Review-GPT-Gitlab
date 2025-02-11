import threading

from reply_module.reply_factory import ReplyFactory


class Reply:
    def __init__(self, config):
        if not isinstance(config, dict):
            raise Exception('Reply config should be a dict.')
        if 'type' not in config:
            raise Exception('Reply config should contain a type field.')
        self.config = config
        self.replies = []
        self.lock = threading.Lock()

    def add_reply(self, reply_msg):
        # reply 格式检查：title, content 必选
        if 'content' not in reply_msg:
            raise Exception('Reply format error, title and content are required.')
        if 'priority' in reply_msg:
            if not isinstance(reply_msg['priority'], int):
                raise Exception('Reply format error, priority should be an integer.')
            elif reply_msg['priority'] == 0:
                self.send_single_message(reply_msg)
                return

        with self.lock:  # 加锁
            self.replies.append(reply_msg)

    def send(self):
        msg_list = {}
        main_msg = None
        with self.lock:  # 加锁
            # 发送所有消息的逻辑
            for msg in self.replies:
                if msg['title'] == '__MAIN_REVIEW__':
                    main_msg = msg
                    continue
                self.__parse_msg(msg, msg_list)

            self.replies = []  # 清空已发送的消息
        if main_msg:
            self.__parse_msg(main_msg, msg_list)
        ret = True
        for target, msg in msg_list.items():
            reply_target = ReplyFactory.get_reply_instance(target, self.config)
            ret &= reply_target.send(msg)
        return ret

    def send_single_message(self, reply):
        """
        实时发送消息
        """
        targets = [t.strip() for t in reply['target'].split(',')]
        if 'all' in targets:
            targets = ReplyFactory.get_all_targets()
        ret = True
        for target in targets:
            reply_target = ReplyFactory.get_reply_instance(target, self.config)
            # 如果title不为__IGNORE__ or __MAIN_REVIEW__, 则发送带有标题的消息
            if 'title' not in reply or reply['title'] not in ['__IGNORE__', '__MAIN_REVIEW__']:
                ret &= reply_target.send(f"## {reply['title']}\n\n{reply['content']}\n\n")
            else:
                ret &= reply_target.send(reply['content'])
        return ret

    def __parse_msg(self, msg, msg_list):
        targets = [t.strip() for t in msg['target'].split(',')]
        if 'all' in targets:
            targets = ReplyFactory.get_all_targets()
        for target in targets:
            msg_list[target] = msg_list.get(target, '')
            # 如果msg['title']不存在
            if 'title' not in msg or msg['title'] in ['__IGNORE__', '__MAIN_REVIEW__']:
                msg_list[target] = f"{msg['content']}\n\n" + msg_list[target]
            else:
                msg_list[target] += f"## {msg['title']}\n\n{msg['content']}\n\n"


if __name__ == '__main__':
    reply = Reply({'type': 'merge_request',
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