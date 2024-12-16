"""For editing lp partitions, like super"""

import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Union

from rom_editor.constants import LPDUMP, LPMAKE, SEVENZIP
from rom_editor.logger import logger


@dataclass
class SuperGroup:
    name: str
    maximum_size: int


@dataclass
class SuperSubPartition:
    """Not really sure if this belongs in super_utils, but I dont have a better place to put it"""

    name: str
    group: str
    attributes: str


@dataclass
class SuperInfo:
    """Class for info about super img. This will be needed for recompiling the super img"""

    metadata_size: int
    super_name: str
    metadata_slot_count: int
    super_size: int
    partitions: List[SuperSubPartition]
    groups: Dict[str, SuperGroup]


def get_super_info(super_img_path: Path) -> SuperInfo:
    """Get info about the super image. This will be needed for recompiling the super img"""
    out = subprocess.check_output([LPDUMP, super_img_path], text=True)
    metadata_size: int = int(re.search(r"Metadata max size: (\d+) bytes", out).group(1))
    super_name: str = re.search(r"Partition name: (\w+)", out).group(1)
    metadata_slot_count: int = int(
        re.search(r"Metadata slot count: (\d+)", out).group(1)
    )
    super_size = int(
        re.search(
            r"Block device table:\n[-=]+\n\s*Partition name: super\n\s*First sector: \d+\n\s*Size:\s*(\d+)\s*bytes",
            out,
        ).group(1)
    )
    groups: Dict[str, SuperGroup] = {}
    pattern = r"Name:\s*(?P<name>.+)\n\s{2}Maximum size:\s*(?P<max_size>\d+)\s*bytes\s*Flags:\s"
    matches = re.finditer(pattern, out)
    for match in matches:
        # Create a SuperGroup object and append to the list
        group = SuperGroup(
            name=match.group("name").strip(),
            maximum_size=int(match.group("max_size")),  # Convert size to int
        )
        groups[group.name] = group

    partitions: List[SuperSubPartition] = []
    pattern = r"Name:\s*(?P<name>.+?)\s*Group:\s*(?P<group>.+?)\s*Attributes:\s*(?P<attributes>.+?)\s*Extents:"
    matches = re.finditer(pattern, out, re.DOTALL)
    for match in matches:
        # Create a Partition object and append to the list
        partition = SuperSubPartition(
            name=match.group("name").strip(),
            group=match.group("group").strip(),
            attributes=match.group("attributes").strip(),
        )
        partitions.append(partition)

    return SuperInfo(
        metadata_size=metadata_size,
        super_name=super_name,
        metadata_slot_count=metadata_slot_count,
        super_size=super_size,
        partitions=partitions,
        groups=groups,
    )


def decompile_super(super_img_path: Path, output_dir: Path) -> None:
    """Decompile a super image"""
    logger.debug(f"Decompiling super at {super_img_path}")
    subprocess.run(
        [SEVENZIP, "x", super_img_path, "-o" + str(output_dir)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def compile_super(
    metadata_size: int,
    super_name: str,
    metadata_slot_count: int,
    partitions: Dict[Path, Union[SuperSubPartition, Dict]],
    groups: List[Union[SuperGroup, Dict]],
    output_path: Path,
    sparse: bool = True,
) -> None:
    """Compile a super image"""
    make_super_cmd = [
        LPMAKE,
        "--metadata-size",
        str(metadata_size),
        "--device-size=auto",
        "--super-name",
        super_name,
        "--metadata-slots",
        str(metadata_slot_count),
    ]
    group_sizes = defaultdict(int)
    for path, partition in partitions.items():
        if isinstance(partition, dict):
            partition = SuperSubPartition(**partition)
        partition_size = path.stat().st_size
        group_sizes[partition.group] += partition_size
        # Now add the partitions to the command
        make_super_cmd += [
            "--partition",
            f"{partition.name}:{partition.attributes}:{partition_size}:{partition.group.name}",
            "--image",
            f"{partition.name}={path}",
        ]

    for group in groups:
        if group.name == "default":
            continue
        if group.name not in group_sizes:
            make_super_cmd += ["--group", f"{group.name}:{group.maximum_size}"]
        else:
            make_super_cmd += ["--group", f"{group.name}:{group_sizes[group.name]}"]
    if sparse:
        make_super_cmd += ["--sparse"]

    make_super_cmd += ["--output", output_path]
    logger.debug(" ".join([str(x) for x in make_super_cmd]))
    subprocess.run(make_super_cmd, check=True)
