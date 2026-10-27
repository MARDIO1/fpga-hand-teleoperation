"""Verify the frozen release, stage its board bundle, and unpack the released HLS IP."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
MODULE = ROOT.parents[1]
RELEASE = MODULE / 'export/bitstream/acz7015/compact-xyz-v0.1.0'

def main():
    info = json.loads((RELEASE / 'build_info.json').read_text())
    for name, expected in info['sha256'].items():
        if hashlib.sha256((MODULE / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Release checksum mismatch: ' + name)
    camera = ROOT / 'overlays/dual_camera_hdmi'
    bundle = camera / 'output/compact_xyz'
    bundle.mkdir(parents=True, exist_ok=True)
    for name in ['pl_stereo_compact_xyz.bit', 'pl_stereo_compact_xyz.hwh', 'resource_gate.txt']:
        shutil.copy2(RELEASE / name, bundle / name)
    groups = {
        camera: ['glove_color_thresholds.json', 'marker_stereo.py'],
        camera / 'hls_markers': ['run_markers_board.py', 'marker_transport.py', 'marker_display_control.py', 'marker_match.cpp', 'marker_match.hpp', 'test_marker_match.cpp', 'geometry_spec.json'],
        camera / 'hls_geometry': ['calibrated_hardware.py', 'calibration.json', 'geometry_registers.json', 'start_compact.py'],
    }
    for folder, names in groups.items():
        for name in names:
            shutil.copy2(folder / name, bundle / name)
    for group, archive in [('hls_markers', 'glove_markers.zip'), ('hls_geometry', 'marker_geometry.zip')]:
        target = ROOT / 'output' / group / 'project/solution1/impl/ip'
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(MODULE / 'export/ip/compact-xyz-v0.1.0' / archive) as package:
            for name in package.namelist():
                if not (target / name).resolve().is_relative_to(target.resolve()):
                    raise ValueError('Unsafe IP archive entry')
            package.extractall(target)
    for name in ['fixtures.txt', 'smoke.txt']:
        shutil.copy2(MODULE / 'data/samples/compact_xyz' / name, ROOT / 'output/hls_geometry' / name)
    print('Checksums verified; board bundle:', bundle)

if __name__ == '__main__':
    main()
