import threading

from large_model.llm_generator import LLMGenerator
from utils.tools import import_submodules

import_submodules('review_engine.handler')

class ReviewEngine:
    def __init__(self, reply):
        self.handles = []
        self.reply = reply
        # 动态导入所有的handle，位置在handle目录下
        from review_engine.abstract_handler import ReviewHandle
        for handle in ReviewHandle.__subclasses__():
            self.handles.append(handle())

    def handle_merge(self, gitlabMergeRequestFetcher, gitlabRepoManager, webhook_info):
        # 多线程处理
        threads = [threading.Thread(target=handle.merge_handle,
                                    args=(gitlabMergeRequestFetcher, gitlabRepoManager, webhook_info, self.reply,
                                          LLMGenerator.new_model())) for handle in self.handles]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        gitlabRepoManager.delete_repo()
        self.reply.send()