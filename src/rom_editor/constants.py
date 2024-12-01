from pathlib import Path

import appdirs

DATA_DIR = Path(appdirs.user_data_dir("kmp-rom-editor", "KosherMyPhone"))
BINARIES_DIR = DATA_DIR / "binaries"


LP_TOOLS_DIR = BINARIES_DIR / "lp_tools"
LPDUMP = LP_TOOLS_DIR / "lpdump"
LPMAKE = LP_TOOLS_DIR / "lpmake"

SEVENZIP = BINARIES_DIR / "7zip" / "7zz"

SIGNAPK = BINARIES_DIR / "signapk" / "signapk.jar"
SIGNAPK_LIBS_DIR = BINARIES_DIR / "signapk" / "libs"

E2FSCK = BINARIES_DIR / "e2fsprogs" / "e2fsck"
RESIZE2FS = BINARIES_DIR / "e2fsprogs" / "resize2fs"
