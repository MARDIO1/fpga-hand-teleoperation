"""Guided individual finger-to-ADC assignment and three-point calibration."""

import argparse
import json
from pathlib import Path
import statistics

from strain_uart import FingerCalibration, StrainSerial


DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data" / "finger_calibration.json"
FINGERS = (("thumb", "拇指"), ("index", "食指"),
           ("middle", "中指"), ("little", "小拇指"))
PINS = ("PA2", "PA0", "PA3", "PA4", "PA5")


def capture(reader, count):
    reader.discard_pending()
    values = [[] for _ in range(5)]
    for _ in range(count):
        frame = reader.read_frame(2.0)
        for channel, value in enumerate(frame.raw):
            if 0 <= value <= 4095:
                values[channel].append(value)
    return [int(statistics.median(channel)) if len(channel) >= count // 2 else None
            for channel in values]


def identify_slot(open_values, closed_values, used):
    changes = [(abs(closed_values[i] - open_values[i]), i)
               for i in range(5) if i not in used
               and open_values[i] is not None and closed_values[i] is not None]
    changes.sort(reverse=True)
    if not changes or changes[0][0] < 30:
        return None
    if len(changes) > 1 and changes[0][0] < changes[1][0] * 1.5:
        return None
    return changes[0][1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="/dev/ttyACM0")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.samples < 10:
        parser.error("at least 10 samples are required")

    fingers = {}
    used = set()
    print("逐指采集：只活动提示的手指，其余手指尽量伸直；保持姿势并按 Enter。")
    with StrainSerial(args.device) as reader:
        reader.read_frame(2.0)
        for name, label in FINGERS:
            while True:
                poses = []
                for pose in ("伸直", "半弯", "自然弯到底"):
                    input("{}{}，保持后按 Enter：".format(label, pose))
                    values = capture(reader, args.samples)
                    poses.append(values)
                    print("  五路原始值 PA2 PA0 PA3 PA4 PA5: {}".format(values))
                changes = [None if poses[0][i] is None or poses[2][i] is None
                           else abs(poses[2][i] - poses[0][i]) for i in range(5)]
                slot = identify_slot(poses[0], poses[2], used)
                print("  各通道伸直到弯曲变化量：{}".format(changes))
                if slot is None:
                    print("  通道不明确；输入 r 重采，或输入 0..4 手动选择。")
                else:
                    print("  建议 slot {} ({})；Enter 确认，r 重采，或输入 0..4 手动选择。".format(slot, PINS[slot]))
                choice = input("  选择：").strip().lower()
                if choice == "r" or (not choice and slot is None):
                    continue
                if choice:
                    if choice not in ("0", "1", "2", "3", "4"):
                        print("  输入无效，重新采集。")
                        continue
                    slot = int(choice)
                points = [pose[slot] for pose in poses]
                if (slot in used or any(value is None for value in points)
                        or not (points[0] < points[1] < points[2] or points[0] > points[1] > points[2])):
                    print("  该槽位已使用、数据无效或三个姿势不单调，请重采。")
                    continue
                fingers[name] = {"slot": slot, "points": points}
                used.add(slot)
                break

    FingerCalibration(fingers)
    document = {"schema": "strain.fingers.v1", "samples_per_pose": args.samples,
                "fingers": fingers}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已保存 {}；无名指跟随小拇指。".format(args.output))


if __name__ == "__main__":
    main()
