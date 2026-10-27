"""Load the curated SO-101 model and add only demo-scene fixtures."""

from __future__ import annotations

from pathlib import Path

import mujoco
import mujoco_menagerie as menagerie


ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".menagerie-cache"


def load_model() -> mujoco.MjModel:
    robot = menagerie.get("robotstudio_so101")
    model_dir = menagerie.Cache(CACHE).resolve(robot)
    spec = mujoco.MjSpec.from_file(str(model_dir / "scene_box.xml"))

    cup = spec.worldbody.add_body(name="cup", pos=[0.42, 0.13, 0.045])
    cup.add_freejoint(name="cup_free")
    cup.add_geom(name="cup", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                 size=[0.028, 0.045, 0.0], mass=0.07,
                 rgba=[0.16, 0.55, 0.92, 1.0], friction=[1.0, 0.03, 0.003])

    target = spec.worldbody.add_body(name="ee_target", mocap=True)
    target.add_geom(name="ee_target_marker", type=mujoco.mjtGeom.mjGEOM_SPHERE,
                    size=[0.012, 0.0, 0.0], rgba=[0.2, 1.0, 0.35, 0.45],
                    contype=0, conaffinity=0)
    return spec.compile()


def collision_groups(model: mujoco.MjModel) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for geom_id in range(model.ngeom):
        if model.geom_contype[geom_id] == 0:
            continue
        body_name = model.body(int(model.geom_bodyid[geom_id])).name
        groups.setdefault(body_name, []).append(geom_id)
    return groups

