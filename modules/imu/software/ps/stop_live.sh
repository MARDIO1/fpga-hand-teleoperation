#!/bin/sh
set -eu
cd /home/xilinx/overlays/mpu6050_studio
if [ -f live.pid ]; then
    pid=$(cat live.pid)
    if [ -r "/proc/$pid/cmdline" ] && tr '\000' ' ' < "/proc/$pid/cmdline" | grep -q 'run_mpu6050.py'; then
        kill -INT "$pid"
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then kill -TERM "$pid"; fi
    fi
fi
