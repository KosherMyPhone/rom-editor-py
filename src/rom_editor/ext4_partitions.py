"""For editing, extracting, and building ext4 partitions"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from rom_editor.constants import E2FSCK, RESIZE2FS
from rom_editor.logger import logger


@dataclass
class Partition:
    name: str
    path: Path


Partitions = list[Partition]


def _get_partition_info(path: Path) -> Partition:
    """Detect what kind of partition we decompiled
    currently supports system, vendor, and product

    :param path: Path to the decompiled ext4 partition
    :type path: Path
    :return: Partition object
    :rtype: Partition
    """
    partition_path = path
    if not partition_path.joinpath("build.prop").is_file():
        partition_path = path / "system"
        if not partition_path.joinpath("build.prop").is_file():
            raise Exception(f"Could not find partition path in {path}")
    build_prop_path = partition_path / "build.prop"
    with build_prop_path.open("r") as f:
        data = f.read()
    if "ro.system.build.date" in data:
        partition_name = "system"
    elif "ro.product.build.date" in data:
        partition_name = "product"
    else:
        partition_name = "vendor"
    return Partition(name=partition_name, path=partition_path)


def decompile_ext4(img_path: Path, output_dir: Path) -> Partition:
    """decompile an ext4 image

    :param img_path: Path to the ext4 image
    :type img_path: Path
    :param output_dir: where to extract the contents of the image
    :type output_dir: Path
    :return: Partition object
    :rtype: Partition
    """
    output_dir.mkdir(exist_ok=True)  # maybe we should say parents=True? Mayebe not.
    logger.info(f"mounting img at {img_path}")
    extract_cmd = ["mount", "-t", "ext4", "-o", "loop", img_path, output_dir]
    subprocess.run(extract_cmd, check=True)
    return _get_partition_info(output_dir)


def unmount_ext4(mounted_dir: Path) -> None:
    """unmount an ext4 image

    :param mounted_dir: where the image is mounted
    :type mounted_dir: Path
    """
    logger.info(f"unmounting {mounted_dir}")
    unmount_cmd = ["umount", mounted_dir]
    subprocess.run(unmount_cmd, check=True)


def increase_ext4_size(img_path: Path, mb_to_add: int) -> None:
    """increase the size of an ext4 image.
    Useful for adding files to the image. We can increase the size and shrink it later,
    so its ok to add extra mb

    :param img_path: Path to the ext4 image
    :type img_path: Path
    :param mb_to_add: how many MB to add to the image
    :type mb_to_add: int
    """
    with img_path.open("ab") as f:
        f.write(b"\0" * (mb_to_add * 1024 * 1024))
    subprocess.run([RESIZE2FS, img_path], check=True)


def repair_ext4(img_path: Path) -> None:
    subprocess.run([E2FSCK, "-yf", img_path], check=True)


def shrink_ext4(img_path: Path) -> None:
    """Shrink an ext4 image

    :param img_path: Path to the ext4 image
    :type img_path: Path
    """
    subprocess.run([RESIZE2FS, "-M", img_path], check=True)
