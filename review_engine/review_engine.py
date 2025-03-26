import threading

from large_model.llm_generator import LLMGenerator
from utils.tools import import_submodules

import_submodules('review_engine.handler')

class ReviewEngine:
    def __init__(self, reply):
        """Initializes a ReviewEngine instance.
        
        Sets the reply attribute and dynamically loads available review handles by importing
        all subclasses of ReviewHandle from the review_engine.abstract_handler module. Each
        handle is instantiated and added to the engine's handles list.
        
        Args:
            reply: An object used to send responses (must implement a send() method).
        """
        self.handles = []
        self.reply = reply
        # 动态导入所有的handle，位置在handle目录下
        from review_engine.abstract_handler import ReviewHandle
        for handle in ReviewHandle.__subclasses__():
            self.handles.append(handle())

    def handle_merge(self, gitlabMergeRequestFetcher, gitlabRepoManager, webhook_info):
        # 多线程处理
        """
        Handle a merge request concurrently.
        
        This method spawns a separate thread for each registered review handle to process the merge.
        Each thread invokes the merge handling operation with the provided merge request fetcher,
        repository manager, webhook information, the reply interface, and a new model instance. Once
        all threads complete, it deletes the repository and sends a reply.
        """
        threads = [threading.Thread(target=handle.merge_handle,
                                    args=(gitlabMergeRequestFetcher, gitlabRepoManager, webhook_info, self.reply,
                                          LLMGenerator.new_model())) for handle in self.handles]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        gitlabRepoManager.delete_repo()
        self.reply.send()