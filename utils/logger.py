import os

import logging

from logging.handlers import TimedRotatingFileHandler

# 日志级别
CRITICAL = 50
FATAL = CRITICAL
ERROR = 40
WARNING = 30
WARN = WARNING
INFO = 20
DEBUG = 10
NOTSET = 0
# Set the current directory
current_dir = os.path.abspath(os.path.dirname(__file__))
# Set the parent directory
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
# Set the current path
CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))
# Set the root path
ROOT_PATH = os.path.join(CURRENT_PATH, os.pardir)
# Set the log path
LOG_PATH = os.path.join(parent_dir, 'logs')


if not os.path.exists(LOG_PATH):
    os.makedirs(LOG_PATH)

class LogHandler(logging.Logger):

    def __init__(self, name, level=INFO, stream=True, file=True):
        self.name = name
        self.level = level
        logging.Logger.__init__(self, self.name, level=level)
        if stream:
            self.__setStreamHandler__()
        if file:
            self.__setFileHandler__()

    def __setFileHandler__(self, level=None):
        """
        set file handler
        :param level:
        :return:
        """
        file_name = os.path.join(LOG_PATH, '{name}.log'.format(name=self.name))
        # 设置日志回滚, 保存在log目录, 一天保存一个文件, 保留15天
        file_handler = TimedRotatingFileHandler(filename=file_name, when='D', interval=1, backupCount=15,
                                                encoding="utf-8")
        file_handler.suffix = '%Y%m%d.log'
        if not level:
            file_handler.setLevel(self.level)
        else:
            file_handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d %(levelname)s | [%(threadName)s] %(name)s [%(lineno)d] | %(filename)s %(funcName)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')

        file_handler.setFormatter(formatter)
        self.file_handler = file_handler
        self.addHandler(file_handler)

    def __setStreamHandler__(self, level=None):

        # Create a stream handler
        stream_handler = logging.StreamHandler()
        # Set the format of the handler
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d %(levelname)s | [%(threadName)s] %(name)s [%(lineno)d] | %(filename)s %(funcName)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')
        stream_handler.setFormatter(formatter)
        # If no level is specified, set the level to the level of the handler
        if not level:
            stream_handler.setLevel(self.level)
        # Otherwise, set the level to the specified level
        else:
            stream_handler.setLevel(level)
        # Add the handler to the logger
        self.addHandler(stream_handler)

    def resetName(self, name):

        # Set the name of the logger
        self.name = name
        # Remove the existing file handler
        self.removeHandler(self.file_handler)
        # Set a new file handler
        self.__setFileHandler__()

project_name = 'chat'
log = LogHandler(project_name, level=DEBUG)
if __name__ == '__main__':
    log.info('this is a test msg')
    log.error("this is a error")
