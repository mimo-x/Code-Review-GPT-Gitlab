import threading

from reply_module.reply_target.reply_factory import ReplyFactory


class Reply:
    def __init__(self, project_id, merge_request_id):
        self.replies = []
        self.lock = threading.Lock()
        self.project_id = project_id
        self.merge_request_id = merge_request_id

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
        markdown_message = ""
        with self.lock:  # 加锁
            # 发送所有消息的逻辑
            for reply in self.replies:
                markdown_message += f"## {reply['title']}\n\n{reply['content']}\n\n"
            self.replies = []  # 清空已发送的消息
        reply_target = ReplyFactory.get_reply_instance(reply['target'], self.project_id, self.merge_request_id)
        return reply_target.send(markdown_message)

    def send_single_message(self, reply):
        """
        实时发送消息
        """
        reply_target = ReplyFactory.get_reply_instance(reply['target'], self.project_id, self.merge_request_id)
        return reply_target.send(reply['content'])


if __name__ == '__main__':
    reply = Reply(9885, 18)
    threads = []
    for i in range(10):
        threads.append(threading.Thread(target=reply.add_reply, args=(
            {'title': f'title{i}', 'content': f'content{i}', 'target': 'gitlab', 'priority': i % 3},)))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    reply.send()