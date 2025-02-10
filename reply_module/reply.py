import threading

from reply_module.reply_target.reply_factory import ReplyFactory


class Reply:
    def __init__(self, project_id, merge_request_iid):
        self.replies = []
        self.lock = threading.Lock()
        self.project_id = project_id
        self.merge_request_iid = merge_request_iid

    def add_reply(self, reply):
        # reply 格式检查：title, content 必选
        if 'title' not in reply or 'content' not in reply:
            raise Exception('Reply format error, title and content are required.')
        if 'priority' in reply:
            if not isinstance(reply['priority'], int):
                raise Exception('Reply format error, priority should be an integer.')
            elif reply['priority'] == 0:
                self.send_single_message(reply)
                return

        with self.lock:  # 加锁
            self.replies.append(reply)

    def send(self):
        msg_list = {}
        with self.lock:  # 加锁
            # 发送所有消息的逻辑
            for reply in self.replies:
                targets = [t.strip() for t in reply['target'].split(',')]
                if 'all' in targets:
                    targets = ReplyFactory.get_all_targets()
                for target in targets:
                    msg_list[target] = msg_list.get(target, '')
                    msg_list[target] += f"## {reply['title']}\n\n{reply['content']}\n\n"
            self.replies = []  # 清空已发送的消息
        ret = True
        for target, msg in msg_list.items():
            reply_target = ReplyFactory.get_reply_instance(target, self.project_id, self.merge_request_iid)
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
            reply_target = ReplyFactory.get_reply_instance(target, self.project_id, self.merge_request_iid)
            ret &= reply_target.send(f"## {reply['title']}\n\n{reply['content']}\n\n")
        return ret


if __name__ == '__main__':
    reply = Reply(9885, 18)
    threads = []
    for i in range(10):
        threads.append(threading.Thread(target=reply.add_reply, args=(
            {'title': f'title{i}', 'content': f'content{i}', 'target': 'gitlab, dingtalk', 'priority': i % 3},)))

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    reply.send()