import argparse
import os
import shutil
import stat
from enum import Enum
from pathlib import Path

import psutil

from rom_editor.constants import binaries_dir
from rom_editor.logger import logger


class ConnectionType(Enum):
    LOCAL = "local"
    REMOTE = "remote"


class DependencyGetter:
    def __init__(self):
        self.deps_dir = binaries_dir
        if not self.deps_dir.is_dir():
            self.deps_dir.mkdir(parents=True)
        else:
            shutil.rmtree(self.deps_dir)
            self.deps_dir.mkdir(parents=True)

    def get_dependencies(self, connection_type: ConnectionType) -> None:
        if not isinstance(connection_type, ConnectionType):
            raise ValueError(f"expected ConnectionType, got {type(connection_type)}")
        if connection_type is ConnectionType.LOCAL:
            self.get_local_deps()
        elif connection_type is ConnectionType.REMOTE:
            raise NotImplementedError("remote dependencies not yet supported")
        for root, dirs, files in self.deps_dir.walk():
            for f in files:
                file = root / f
                if file.is_file() and not file.suffix:  # binary executables
                    current_permissions = stat.S_IMODE(os.stat(file).st_mode)
                    new_permissions = (
                        current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                    )
                    os.chmod(file, new_permissions)

    def get_local_deps(self):
        # We will look for kmpromkitchendeps.zip in all filesystems
        # Generally I would use all=False, but sometimes someone will not
        # have an external drive etc so he can make his own mount
        # Also, development is done in WSL and all=False doesnt show usb
        # drives we mounted using  `sudo mount -t drvfs X: /mnt/x`
        partitions = psutil.disk_partitions(all=True)
        for partition in partitions:
            deps_zip = Path(partition.mountpoint) / "kmpromkitchendeps.zip"
            if deps_zip.is_file():
                shutil.unpack_archive(deps_zip, self.deps_dir)
                return

        raise FileNotFoundError("could not find local dependencies")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("type", choices=["local", "remote"])
    args = parser.parse_args()
    logger.info(f"Getting {args.type} dependencies")
    DependencyGetter().get_dependencies(ConnectionType(args.type))
    logger.info("Completed Successfully")
