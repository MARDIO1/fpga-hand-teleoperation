"""Small point-table updates and optional atomic, same-snapshot image packets."""
import io
import json
import math
import os
from pathlib import Path
import struct

import numpy as np

HEADER = struct.Struct('<4sII')
FRAME_BYTES = 1280*720*2
MAX_METADATA_BYTES = 1024*1024


def snapshot_due(now, last, fps):
    if not math.isfinite(fps) or fps < 0:
        raise ValueError('Snapshot rate must be finite and nonnegative')
    return fps > 0 and (last is None or now-last >= 1/fps)


def publish_points(output, result):
    target = Path(output)/'latest.json'
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result,separators=(',',':'),allow_nan=False),encoding='utf-8')
    os.replace(str(temporary),str(target))


def publish_snapshot(output, frame, result, file_format='bin'):
    if frame.shape != (720,1280) or frame.dtype != np.dtype('<u2') or not frame.flags.c_contiguous:
        raise ValueError('Expected contiguous 1280x720 RGB565 snapshot')
    metadata = json.dumps(result,separators=(',',':'),allow_nan=False).encode('utf-8')
    if len(metadata) > MAX_METADATA_BYTES:
        raise ValueError('Snapshot metadata too large')
    if file_format not in ('bin','npz'):
        raise ValueError('Unknown snapshot format')
    target = Path(output)/('latest.'+file_format)
    temporary = target.with_suffix(target.suffix+'.tmp')
    with temporary.open('wb') as stream:
        if file_format == 'bin':
            stream.write(HEADER.pack(b'MKR1',FRAME_BYTES,len(metadata)))
            stream.write(memoryview(frame).cast('B'))
            stream.write(metadata)
        else:
            # Compatibility only; the old NumPy ZIP path is expensive on the board.
            np.savez(stream,frame=frame,metadata=np.array(metadata.decode('utf-8')))
    os.replace(str(temporary),str(target))


def decode_snapshot(data):
    if data[:4] == b'MKR1':
        if len(data)<HEADER.size:
            raise ValueError('Truncated snapshot header')
        magic,frame_bytes,metadata_bytes = HEADER.unpack_from(data)
        if (frame_bytes!=FRAME_BYTES or metadata_bytes>MAX_METADATA_BYTES
                or len(data)!=HEADER.size+frame_bytes+metadata_bytes):
            raise ValueError('Invalid snapshot lengths')
        frame = np.frombuffer(data,dtype='<u2',count=720*1280,offset=HEADER.size).reshape(720,1280)
        result = json.loads(data[HEADER.size+frame_bytes:].decode('utf-8'))
        return frame,result
    if data[:2] != b'PK':
        raise ValueError('Unknown snapshot format')
    with np.load(io.BytesIO(data),allow_pickle=False) as archive:
        frame = archive['frame']
        result = json.loads(str(archive['metadata']))
    if frame.shape!=(720,1280) or frame.dtype!=np.dtype('<u2'):
        raise ValueError('Invalid NPZ frame')
    return frame,result


def stage_eye(pixels, scratch, memory, offset):
    if (pixels.shape!=(720,640) or pixels.dtype!=np.dtype('<u2')
            or scratch.shape!=pixels.shape or scratch.dtype!=pixels.dtype
            or not scratch.flags.c_contiguous or offset<0 or offset+scratch.nbytes>len(memory)):
        raise ValueError('Invalid eye staging buffers')
    # Preallocated cached CPU scratch, then existing noncached DMA staging mapping.
    # No new physical addresses, cache aliases or cache-maintenance assumptions.
    np.copyto(scratch,pixels,casting='no')
    memory[offset:offset+scratch.nbytes] = memoryview(scratch).cast('B')
    return scratch.nbytes
