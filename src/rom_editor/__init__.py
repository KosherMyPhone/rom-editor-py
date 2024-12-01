import time

from rom_editor.logger import logger
from rom_editor.utils import is_root

__version__ = "0.1.0"

logger.debug(f"Starting kmp_rom_editor {__version__}")
if not is_root():
    """Most things inside mounted ext4 partitions need root access. There are likely better ways to do it, but the development time to make a better way is not worth it. Root will have to do. Use docker if you want. """
    logger.warning(
        "root access not found. many likely functions will not work. Resuming in 3 seconds..."
    )
    time.sleep(3)
