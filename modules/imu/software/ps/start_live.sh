#!/bin/sh
set -eu
cd /home/xilinx/overlays/mpu6050_studio
if [ -f live.pid ] && kill -0 "$(cat live.pid)" 2>/dev/null; then
    echo "An IMU capture is already running"
    exit 1
fi
nohup python3 -u run_mpu6050.py --seconds "${1:-3600}" --output pose.jsonl > live_stdout.log 2> stats.log < /dev/null &
echo "$!" > live.pid
echo "IMU capture PID: $(cat live.pid)"
