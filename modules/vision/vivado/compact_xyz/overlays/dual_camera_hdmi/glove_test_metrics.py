"""Timing summaries and one-to-one, color-aware point evaluation."""

import math

import numpy as np

from marker_detection import COLORS


def timing_summary(records, warmup=2):
    measured = records[warmup:]
    def hz(key):
        if len(records) < 2:
            return None
        duration = records[-1][key] - records[0][key]
        return (len(records)-1) / duration if duration > 0 else None
    stages = {}
    for key in ('detector_ms', 'matching_ms', 'decode_ms', 'render_ms', 'processing_ms', 'save_ms', 'receive_wait_ms'):
        values = [r[key] for r in measured if key in r]
        if values:
            stages[key] = dict(median=float(np.median(values)), p95=float(np.percentile(values, 95)))
    detector = stages.get('detector_ms', {}).get('median')
    return dict(processed_snapshots=len(records), warmup_frames=warmup, timed_frames=len(measured),
                received_hz=hz('received_s'), processed_hz=hz('completed_s'), stages_ms=stages,
                detector_only_capacity_hz=1000/detector if detector else None,
                accuracy=None, accuracy_status='Requires complete human annotations; counts are not accuracy.',
                source_frame_id_available=False, exposure_to_result_latency_ms=None,
                fps_note='Host snapshot rates, not unique camera frames or exposure latency. '
                'Observed rates include capture/SSH, processing, display and previous disk writes.')


def evaluate_points(predictions, truth, radius=12):
    """Maximum-cardinality bipartite match; repeats of a color remain distinct."""
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError('Matching radius must be finite and positive')
    for point in list(predictions) + list(truth):
        if (point.get('color') not in COLORS or not all(
                isinstance(point.get(k), (int, float)) and not isinstance(point.get(k), bool)
                and math.isfinite(point[k]) and 0 <= point[k] < limit
                for k, limit in (('u', 640), ('v', 720)))):
            raise ValueError('Points need a known color and finite eye-local u/v coordinates')
    edges = []
    for target in truth:
        matches = [(math.hypot(p['u']-target['u'], p['v']-target['v']), i)
                   for i, p in enumerate(predictions) if p['color'] == target['color']]
        edges.append([i for distance, i in sorted(matches) if distance <= radius])
    owner = {}
    def augment(target, seen):
        for prediction in edges[target]:
            if prediction in seen:
                continue
            seen.add(prediction)
            if prediction not in owner or augment(owner[prediction], seen):
                owner[prediction] = target
                return True
        return False
    for index in range(len(truth)):
        augment(index, set())
    tp = len(owner)
    fp, fn = len(predictions)-tp, len(truth)-tp
    return dict(tp=tp, fp=fp, fn=fn, precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
