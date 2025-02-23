import xml.etree.ElementTree as ET
import zipfile
from ast import Set
from base64 import b64encode
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Tuple

import xattr
from apk_editor import sign
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, pkcs7

from rom_editor.ext4_partitions import Partition, Partitions
from rom_editor.logger import logger


class RomResigner:
    def __init__(
        self,
        partitions: Partitions,
        signing_keys: Dict["str", sign.SigningKey],
    ):
        self.partitions = partitions
        self.signing_keys = signing_keys
        self.total_processed = 0
        self.resigned = 0
        self.skipped = 0

    def _find_mac_permissions_file(self, partition: Partition) -> Path:
        for file in (partition.path / "etc" / "selinux").iterdir():
            if "mac_permissions.xml" in file.name:
                return file

    def _parse_mac_permissions_file(self, mac_permissions_file: Path) -> Dict[str, str]:
        signatures = {}
        root = ET.parse(mac_permissions_file).getroot()
        for signer in root:
            if signer.tag == "signer":
                for seinfo in signer:
                    if seinfo.tag == "seinfo":
                        signatures[seinfo.attrib["value"]] = signer.attrib["signature"]
        return signatures

    def _get_files_to_sign(self, partition: Partition) -> List[Path]:
        to_sign: List[Path] = []
        for root, _, files in partition.path.walk():
            for name in files:
                file = root / name
                if file.name.endswith((".apk", ".jar", ".apex")):
                    to_sign.append(file)
        return to_sign

    def _get_cert(self, file: Path) -> Tuple[bool, bytes]:
        with zipfile.ZipFile(file) as zip:
            # first check if the META-INF/CERT file exists
            to_extract = "META-INF/CERT.RSA"
            if to_extract in zip.namelist():
                with zip.open("META-INF/CERT.RSA") as f:
                    cert_chain = pkcs7.load_der_pkcs7_certificates(f.read())
                    return True, cert_chain[0].public_bytes(Encoding.PEM)
            else:
                return False, b""

    def _verify_signature(
        self, cert: bytes, mac_permissions_signatures: Dict
    ) -> str | None:
        for name, signature in mac_permissions_signatures.items():
            sig_bytes = bytes.fromhex(signature)
            if b64encode(sig_bytes) in cert.replace(b"\n", b""):
                return name
        return None

    def _signing_key_to_der(self, signing_key: sign.SigningKey) -> bytes:
        with signing_key.x509_path.open("rb") as f:
            d = f.read()
        cert = x509.load_pem_x509_certificate(d)
        return cert.public_bytes(Encoding.DER).hex()

    def _update_mac_permissions_file(
        self, mac_permissions_file: Path, used_signatures: Set
    ):
        tree = ET.parse(mac_permissions_file)
        root = tree.getroot()
        for signer in root:
            if signer.tag == "signer":
                for seinfo in signer:
                    if seinfo.tag == "seinfo":
                        if seinfo.attrib["value"] in used_signatures:
                            signer.attrib["signature"] = self._signing_key_to_der(
                                self.signing_keys[seinfo.attrib["value"]]
                            )
        tree.write(mac_permissions_file)

    def _process_apk(self, file: Path, mac_permissions_signatures: Dict):
        success, cert = self._get_cert(file)
        if not success:
            logger.debug(f"{file.name} - No Signature found => skipping")
            self.skipped += 1
            return
        sig_to_use = self._verify_signature(cert, mac_permissions_signatures)
        if not sig_to_use:
            logger.debug(f"{file.name} - Unknown signature => skipping")
            self.skipped += 1
            return
        if not self.signing_keys.get(sig_to_use):
            logger.debug(f"{file.name} - No key found for {sig_to_use} => skipping")
            self.skipped += 1
            return
        attrs = xattr.xattr(file)
        current_context = attrs.get("security.selinux")
        sign.sign_apk(file, self.signing_keys[sig_to_use])
        self.used_signatures.add(sig_to_use)
        logger.debug(f"{file.name} - Signed as {sig_to_use}")
        attrs.set("security.selinux", current_context)
        logger.debug(f"{file.name} - Restored context")
        self.resigned += 1

    def resign(self, use_threads: bool = False):
        for partition in self.partitions:
            self.used_signatures = set()
            mac_permissions_file = self._find_mac_permissions_file(partition)
            if not mac_permissions_file:
                logger.debug(f"No mac permissions file found for {partition.name}")
                continue
            logger.debug(
                f"Found mac permissions file for {partition.name} at {mac_permissions_file}"
            )
            mac_permissions_signatures = self._parse_mac_permissions_file(
                mac_permissions_file
            )
            to_sign = self._get_files_to_sign(partition)
            logger.debug(f"Found {len(to_sign)} files to sign for {partition.name}")
            futures: list[Future] = []
            if use_threads:
                with ThreadPoolExecutor() as executor:
                    for file in to_sign:
                        futures.append(
                            executor.submit(
                                self._process_apk, file, mac_permissions_signatures
                            )
                        )
                    for future in futures:
                        future.result()
            else:
                for file in to_sign:
                    self._process_apk(file, mac_permissions_signatures)

            self._update_mac_permissions_file(
                mac_permissions_file, self.used_signatures
            )
            logger.debug(f"Updated mac permissions file for {partition.name}")
            logger.debug(
                f"{self.resigned} signed; {self.skipped} skipped in partition {partition.name}"
            )
