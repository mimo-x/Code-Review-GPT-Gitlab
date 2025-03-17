import server.server as server
from utils.args_check import check_config


if __name__ == '__main__':
    check_config()
    server.run()