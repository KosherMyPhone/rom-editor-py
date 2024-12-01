import logging

from rich.logging import RichHandler

logger = logging.getLogger("kmp_rom_editor")
logger.setLevel(logging.DEBUG)
# handler = logging.StreamHandler()
# We may want to bring this back but for now we are expirimenting with rich
handler = RichHandler(
    show_level=True,
    show_path=False,
    show_time=False,
)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
