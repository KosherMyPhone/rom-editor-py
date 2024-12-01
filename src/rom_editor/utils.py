import os


def is_root() -> bool:
    return os.geteuid() == 0
