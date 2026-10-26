"""Prepare the local MANO/MuJoCo runtime without redistributing MANO assets."""

from __future__ import annotations

import argparse
import pickle
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
UPSTREAM = RUNTIME / "DexHOI2Sim"
HAND_OUTPUT = RUNTIME / "mano_hand"
UPSTREAM_URL = "https://github.com/taeyunwoo/DexHOI2Sim.git"
UPSTREAM_COMMIT = "9bfad7593eb2733fa5951787755f7ed320edea88"
MODEL_NAMES = ("MANO_RIGHT.pkl", "MANO_LEFT.pkl")


class _ChumpyValue:
    """Minimal unpickling target for legacy arrays stored by MANO v1.2."""

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
        else:
            self.state = state


class _ManoUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        if module.startswith("chumpy"):
            return _ChumpyValue
        return super().find_class(module, name)


def _plain_array(value):
    if isinstance(value, _ChumpyValue) and "idxs" in value.__dict__:
        source = _plain_array(value.a).reshape(-1)
        return source[value.idxs].reshape(value.preferred_shape)
    if isinstance(value, _ChumpyValue) and "x" in value.__dict__:
        return np.asarray(value.x)
    return value


def _run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def _prepare_upstream() -> None:
    if not UPSTREAM.exists():
        _run("git", "clone", UPSTREAM_URL, str(UPSTREAM))
    safe = f"safe.directory={UPSTREAM.as_posix()}"
    _run("git", "-c", safe, "-C", str(UPSTREAM), "checkout", UPSTREAM_COMMIT)


def _extract_models(archive: Path) -> Path:
    assets = UPSTREAM / "mano2urdf" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for name in MODEL_NAMES:
            member = f"mano_v1_2/models/{name}"
            with bundle.open(member) as source, (assets / name).open("wb") as target:
                shutil.copyfileobj(source, target)
    return assets


def _sanitize_models(assets: Path) -> None:
    target = UPSTREAM / "mano2urdf" / "outputs" / "_smplx_root" / "mano"
    target.mkdir(parents=True, exist_ok=True)
    for name in MODEL_NAMES:
        with (assets / name).open("rb") as stream:
            model = _ManoUnpickler(stream, encoding="latin1").load()
        model = {key: _plain_array(value) for key, value in model.items()}
        with (target / name).open("wb") as stream:
            pickle.dump(model, stream, protocol=2)


def _generate_hand() -> None:
    generator = UPSTREAM / "mano2urdf" / "scripts" / "generate_urdf.py"
    _run(
        sys.executable,
        str(generator),
        "--betas",
        "0,0,0,0,0,0,0,0,0,0",
        "--is_rhand",
        "--out",
        str(HAND_OUTPUT),
        "--name",
        "teleop_hand",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mano_zip", type=Path, help="official mano_v1_2.zip")
    args = parser.parse_args()
    archive = args.mano_zip.resolve()
    if not archive.is_file():
        raise FileNotFoundError(archive)
    _prepare_upstream()
    assets = _extract_models(archive)
    _sanitize_models(assets)
    _generate_hand()
    print(f"MANO runtime ready: {HAND_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
