"""Verify this release and unpack frozen IP for a standalone rebuild."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
MODULE = ROOT.parents[1]
RELEASE = MODULE / "export/bitstream/acz7015/optimized-xyz-v0.2.0"


def main():
    manifest = json.loads((RELEASE / "build_info.json").read_text())
    for name, expected in manifest["sha256"].items():
        if hashlib.sha256((MODULE / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Release checksum mismatch: " + name)
    for group in ("markers", "geometry"):
        target = ROOT / "ip" / group
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(MODULE / "export/ip/optimized-xyz-v0.2.0" / (group + ".zip")) as package:
            for name in package.namelist():
                if not (target / name).resolve().is_relative_to(target.resolve()):
                    raise ValueError("Unsafe IP entry: " + name)
            package.extractall(target)
    print("All release checksums verified; frozen IP unpacked.")


if __name__ == "__main__":
    main()
