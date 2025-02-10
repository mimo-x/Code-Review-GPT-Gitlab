import threading

from utils.tools import import_submodules

import_submodules('review_engine.handler')

class ReviewEngine:
    def __init__(self, reply):
        self.handles = []
        self.reply = reply
        # 动态导入所有的handle，位置在handle目录下
        from .handler.abstract_handler import ReviewHandle
        for handle in ReviewHandle.__subclasses__():
            self.handles.append(handle())

    def handle_merge(self, changes, merge_info, webhook_info):
        # 多线程处理
        threads = [threading.Thread(target=handle.merge_handle, args=(changes, merge_info, webhook_info, self.reply))
                   for handle in self.handles]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.reply.send()






