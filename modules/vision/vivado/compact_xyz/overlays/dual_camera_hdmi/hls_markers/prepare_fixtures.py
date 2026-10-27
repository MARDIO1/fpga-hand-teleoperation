"""Generate HLS golden fixtures with the independently verified Python model."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from glove_rle_reference import classify565, opencv_components, rle_components
from marker_detection import load_thresholds
from preview_downsample import load_rgb565


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE.parents[2] / "output/hls_markers/fixtures")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = load_thresholds()
    cases = []

    def save(name, pixels, eye="L", error=0, min_area=1, max_area=460800, protocol_bad=False):
        classes, _ = classify565(pixels, config[eye])
        regions, statistics = rle_components(classes)
        assert regions == opencv_components(classes), name
        height, width = pixels.shape
        accepted = [r for r in regions if min_area <= r["area"] <= max_area and r["xmin"] > 0
                    and r["ymin"] > 0 and r["xmax"] < width-1 and r["ymax"] < height-1]
        if error:
            accepted = []
        stem = output / name
        pixels.astype("<u2").tofile(str(stem) + ".rgb565")
        lines = [f"{width} {height} {error} {int(protocol_bad)} {min_area} {max_area}"]
        lines += [" ".join(str(config[eye][color][key]) for key in ("h_min", "h_max", "s_min", "v_min"))
                  for color in ("red", "yellow", "green", "blue")]
        lines.append(str(len(accepted)))
        lines += [" ".join(str(r[key]) for key in ("color_id", "area", "sum_x", "sum_y", "xmin", "ymin", "xmax", "ymax")) for r in accepted]
        (output / f"{name}.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
        cases.append(str(stem))
        return statistics

    save("empty", np.zeros((12, 20), np.uint16))
    save("full", np.full((12, 20), 0xF800, np.uint16))
    bridge = np.zeros((12, 20), np.uint16)
    bridge[2:6, 3] = 0xF800
    bridge[2:6, 7] = 0xF800
    bridge[5, 3:8] = 0xF800
    bridge[8, 13] = bridge[9, 14] = 0x001F
    save("bridge_diagonal", bridge)
    save("protocol_bad", bridge, error=2, protocol_bad=True)
    save("recovery_after_bad", bridge)
    gap = np.zeros((10, 20), np.uint16)
    gap[2, 2:4] = gap[6, 2:4] = 0x07E0
    save("empty_rows", gap)
    save("one_pixel", np.array([[0xF800]], np.uint16))
    save("full_large", np.full((720, 640), 0xF800, np.uint16))
    alternating = np.tile(np.array([0xF800, 0x001F], np.uint16), (6, 320))
    save("max_row_runs", alternating)
    overflow = np.zeros((32, 640), np.uint16)
    overflow[::2, ::2] = 0xF800
    assert save("label_overflow", overflow, error=4)["allocated_labels"] > 2047
    save("recovery_after_overflow", bridge)
    rng = np.random.default_rng(12)
    palette = np.array([0, 0, 0, 0xF800, 0x07E0, 0x001F, 0xFFE0], np.uint16)
    for index in range(12):
        save(f"random_{index:02d}", palette[rng.integers(0, len(palette), (24, 37))])
    paths = sorted((HERE.parents[2] / "output/glove_preview/live").glob("sample_*.rgb565"))
    for index, path in enumerate(paths):
        frame = load_rgb565(path)
        for eye, pixels in (("L", frame[:, 640:]), ("R", frame[:, :640])):
            statistics = save(f"real_{index:02d}_{eye}", pixels, eye,
                              min_area=config["min_area"], max_area=config["max_area"])
            assert statistics["allocated_labels"] < 2048
    # Quantization oracle: compare every RGB565 value for both eye configs.
    all_colors = np.arange(65536, dtype=np.uint16).reshape(256, 256)
    for eye in ("L", "R"):
        classes, _ = classify565(all_colors, config[eye])
        classes.tofile(output / f"colors_{eye}.bin")
    (output / "manifest.txt").write_text("\n".join(cases) + "\n", encoding="ascii")
    smoke = cases[:7] + cases[9:12] + cases[23:25]
    (output / "smoke.txt").write_text("\n".join(smoke) + "\n", encoding="ascii")
    (output / "summary.json").write_text(json.dumps(dict(cases=len(cases), real_stereo_pairs=len(paths),
                                                        config=config), indent=2), encoding="utf-8")
    print(f"Generated {len(cases)} cases ({len(paths)} stereo pairs) in {output}")


if __name__ == "__main__":
    main()
