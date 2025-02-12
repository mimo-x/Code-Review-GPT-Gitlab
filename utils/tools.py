import importlib
import os
import pkgutil
import sys


def import_submodules(package_name):
    # 确保正确的工作目录
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    package = importlib.import_module(package_name)
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package_name}.{module_name}")


if __name__ == "__main__":
    from review_engine.review_engine import ReviewEngine
    from reply_module.reply import Reply
    re = ReviewEngine(Reply(9885, 18))
    re.handle_merge("changes", "info")