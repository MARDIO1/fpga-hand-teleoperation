# 精简双目PL/PS XYZ上板验收

2026-10-26 已编译、上板并完成PC先验对照。HDMI输出、显示HLS核、显示MM2S和按键GPIO均已移除。

| 整板资源 | 数量 | 占用 |
|---|---:|---:|
| LUT | 26754 | 57.91% |
| 寄存器 | 29790 | 32.24% |
| BRAM36 tile | 38.5 | 40.53% |
| DSP | 64 | 40.00% |

各类资源均低于60%。100MHz实现后建立时间余量+0.572ns、保持时间余量+0.040ns；发布脚本和部署脚本均检查资源上限。

PL计算：颜色/RLE/CCL、稀疏去畸变与极线校正、DLT三角化、左相机坐标变换及重投影检查。PS计算：可替换候选筛选、与PC同逻辑的C++一对一匹配、DMA及数据发布。PC仅显示，不参与板端识别与XYZ。

标定文件：session_20261026_13p6mm/solution/candidate_calibration.npz，SHA256 ce8610fed55be9c0b8ba0b4c1a66e3334500ce4ce4a8796222abb94be883c978。实验性毫米坐标，物理左摄像头光心为原点，X右、Y下、Z前。

验证：384点C仿真、12点Verilog协同仿真通过；15组历史图共130对XYZ与PC先验一致。板端回放5对，实时分别验证8对和7对；XYZ最大差约8.53e-13mm，配对及重投影门控一致。这个差值是实现一致性，不是实际测距误差。

实时最近30周期：采集29.7FPS、完整更新8.61Hz、平均周期116.1ms、P95 151.8ms；图像预览独立2Hz。短回放计算约55ms/对不能当作持续完整帧率。

板端目录：/home/xilinx/overlays/pl_stereo_hdmi/compact_xyz_20261026。当前运行run_markers_board.py --calibrated --frames 0 --fps 30 --snapshot-fps 2。最新点表/dev/shm/marker_results/latest.json，同帧快照latest.bin。

PC：python overlays/dual_camera_hdmi/hls_markers/preview_markers_board.py --output output/glove_preview/compact_xyz_live。

边界：绝对精度尚未认证，点ID为单帧编号，DDR快照可能撕裂且不保证曝光同步。保留原相机非专用PCLK布线约束；未配置重启自动加载，旧HDMI版本可用于恢复。
