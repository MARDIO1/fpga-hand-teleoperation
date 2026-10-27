"""Sparse candidate matching suitable for PS; no dense images or metric XYZ.

Default geometry uses the old 4.12 px right-image shift only. It is a diagnostic
gate, not calibrated rectification. Pair IDs are local to the current snapshot.
"""

import math


DEFAULT_MATCHING = dict(right_y_shift_px=4.12, max_vertical_error_px=6.0,
                        min_disparity_px=20.0, max_disparity_px=190.0,
                        max_area_ratio=4.0, uniqueness_margin=0.15)
COLORS = ('red', 'yellow', 'green', 'blue')


def match_markers(left, right, settings=None, coordinate_space='raw'):
    if coordinate_space not in ('raw','rectified'):
        raise ValueError('Unknown coordinate space')
    cfg = DEFAULT_MATCHING.copy()
    if settings is not None:
        if not isinstance(settings, dict) or set(settings) - set(cfg):
            raise ValueError('Unknown sparse matching settings')
        cfg.update(settings)
    if any(isinstance(v, bool) or not isinstance(v,(int,float)) or not math.isfinite(v)
           for v in cfg.values()):
        raise ValueError('Matching settings must be finite numbers')
    if (cfg['max_vertical_error_px'] <= 0 or cfg['max_area_ratio'] <= 1
            or cfg['uniqueness_margin'] <= 0
            or not 0 <= cfg['min_disparity_px'] <= cfg['max_disparity_px'] <= 639):
        raise ValueError('Invalid matching bounds')
    for point in list(left)+list(right):
        if (point.get('color') not in COLORS or any(
                isinstance(point.get(k), bool) or not isinstance(point.get(k),(int,float))
                or not math.isfinite(point[k])
                or (coordinate_space=='raw' and not 0 <= point[k] < maximum)
                for k, maximum in (('u',640),('v',720)))
                or isinstance(point.get('area_px'),bool) or not isinstance(point.get('area_px'),(int,float))
                or not math.isfinite(point['area_px']) or not 0 < point['area_px'] <= 640*720):
            raise ValueError('Invalid marker coordinates, color, or area')
    costs, rows, columns = {}, [[] for _ in left], [[] for _ in right]
    for i, lp in enumerate(left):
        for j, rp in enumerate(right):
            if lp['color'] != rp['color']:
                continue
            disparity = lp['u']-rp['u']
            vertical = lp['v']-(rp['v']+cfg['right_y_shift_px'])
            ratio = max(lp['area_px'],rp['area_px'])/min(lp['area_px'],rp['area_px'])
            if (not cfg['min_disparity_px'] <= disparity <= cfg['max_disparity_px']
                    or abs(vertical) > cfg['max_vertical_error_px'] or ratio > cfg['max_area_ratio']):
                continue
            cost = abs(vertical)/cfg['max_vertical_error_px'] + 0.35*math.log(ratio)/math.log(cfg['max_area_ratio'])
            costs[i,j] = (cost,disparity,vertical)
            rows[i].append((cost,j))
            columns[j].append((cost,i))
    def unique_best(options):
        options.sort()
        if not options:
            return None
        if len(options)>1 and options[1][0]-options[0][0] < cfg['uniqueness_margin']:
            return None
        return options[0][1]
    best_right = [unique_best(row) for row in rows]
    best_left = [unique_best(column) for column in columns]
    pairs = []
    for i,j in enumerate(best_right):
        if j is None or best_left[j] != i:
            continue
        cost,disparity,vertical = costs[i,j]
        pairs.append(dict(pair_id=len(pairs)+1, left_index=i, right_index=j,
                          color=left[i]['color'], left_uv=[left[i]['u'],left[i]['v']],
                          right_uv=[right[j]['u'],right[j]['v']], disparity_px=disparity,
                          vertical_residual_px=vertical, cost=cost, xyz_mm=None))
    used_left = {p['left_index'] for p in pairs}
    used_right = {p['right_index'] for p in pairs}
    return dict(pairs=pairs, unmatched_left=[i for i in range(len(left)) if i not in used_left],
                unmatched_right=[i for i in range(len(right)) if i not in used_right],
                gated_edges=len(costs), settings=cfg, pair_identity='snapshot_local_only',
                geometry_status='provisional_vertical_shift_not_validated_rectification',
                metric_valid=False, source_exposure_synchronization='unverified')
