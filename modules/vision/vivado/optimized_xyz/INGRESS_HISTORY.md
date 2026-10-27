# Compact V2 整板接入（2026-10-27，上板前）

## 实际实现

独立工程 `E:/fpga_learn/biv2/vxyz.xpr`，独立产物目录 `../output/compact_ingress_v2/`。不打开原 compact 工程，不覆盖原 bit/hwh，不连接或更新板子。

数据路径：相机 → 单帧门控 → capture VDMA → DDR → direct reader → 原 glove_markers → 原320/64结果打包 → S2MM结果DMA → 原PS C++匹配及PL geometry。

保留原颜色HLS/阈值、候选筛选、配对和标定数学。移除 marker DMA 的 MM2S 输入通道，旧 bridge 仅保留结果打包功能（输入部分常量绑定后由综合移除）。无HDMI、无按键、无双输入mux。回退使用原compact bit/hwh及原驱动，不在新硬件里常驻两套输入。

## 同帧与所有权

使用两个2MiB间隔槽0x1e000000和0x1e200000；0x1e600000保留可用。每帧1,843,200字节，避开原0x1e400000输入和0x1e500000结果区，全部在原16MiB no-map预留区内。

采集门控只在收到完整新SOF后放行一帧，之后继续消耗并丢弃相机流，禁止VDMA循环覆盖。PS等待门控EOF及VDMA IOC共同成立，才提交lease；IOC是DDR写完成判定，GPIO源帧数不能替代。PS拥有VDMA配置权限，须使用配套驱动，不得并发运行旧capture控制程序。

左右眼由同一lease读取。硬件拒绝在leased槽上重新arm采集，reader忙时拒绝release。处理A槽时可一次采集B槽；B采满后等待A处理完成，不自动覆盖。处理和可选快照全部结束后释放A、取得B，再启动A采集。没有显示读引用，也不建立帧队列。

时间戳为100MHz计数器换算的PL视频SOF微秒，不是已验证曝光时间。source_frame_id来自送入门控的SOF计数，作为本次PL重载期间的generation；两传感器曝光同步、真实毫米精度仍待板上验收。

错误为fail-stop：reader响应错误、gate格式错误、VDMA错误或超时均停止输出新点表，不回收可能仍有AXI事务的槽。reader abort会排空已接受突发，永不返回的总线事务不能仅靠复位读图模块恢复；须先诊断并安全停止/重载整个overlay。

## 控制地址

原地址保留：VDMA 0x43000000；camera GPIO 0x41200000；结果DMA 0x40400000（只有S2MM）；颜色0x43c20000；geometry 0x43c40000。新增ingress 0x43c60000。

下表是当前已实现寄存器，替代原README的拟定布局。控制写使用全32位、每次一个命令；采集基址与VDMA实际目标必须由同一控制进程设置一致。

| 偏移 | 字段 |
|---|---|
| 0x00 | ID=0x4d495632 |
| 0x04 | 实现版本/能力=0x20b：direct、lease及单帧门控，无显示 |
| 0x08 | 命令：1读单眼；2中止reader；4清控制错误；8释放lease；16提交已写完帧lease |
| 0x0c | bit0 reader busy，1 done，2 reader/命令错误；8 armed，9 capturing，10 capture EOF，11 leased，12 gate error |
| 0x10 | capture_base，仅三槽白名单，采集中或未消费完成帧时禁止修改 |
| 0x14 | 固定stride=2560（只读） |
| 0x18 | reader eye：0物理R，1物理L |
| 0x1c | lease source_frame_id（只读） |
| 0x20/24 | lease SOF timestamp_us低/高（只读） |
| 0x28 | lease base（只读） |
| 0x2c | bit0..3 reader错误，bit4控制错误，bit5 gate错误 |
| 0x30 | reader已发送像素数（只读） |
| 0x34 | 写1 arm下一完整采集帧；读capture frame_id |
| 0x38 | bit0颜色/结果DMA分支reset释放，默认0；reader忙时禁止修改 |
| 0x3c | capture已发送像素数（只读） |

## 重建与验证

`simulate_reader.ps1`：完整双眼、逐像素值/地址、随机背压、AXI错误、abort、恢复。

`simulate_control.ps1`：AXI-Lite独立地址/数据握手及读背压、完整帧门控、部分旧帧丢弃、禁止覆盖leased槽、另一槽并行采集、reader descriptor及abort排空。

`python -m unittest discover -s overlays/dual_camera_hdmi/marker_ingress_v2 -p 'test_*.py' -v`：原所有权模型及新PS驱动协议检查，包含EOF+IOC双条件、DMA错误不授予lease、非预留槽拒绝、同点表解析兼容与禁止整图搬运。

独立构建：Vivado batch执行本目录 `build_ingress.tcl`。`finish_ingress.tcl` 在布局布线后检查四类资源全部≤60%、setup/hold均≥0，再生成release bit/hwh。实现报告和资源门禁在compact_ingress_v2产物目录。硬件检查未通过时不得把旧文件当成新release。

`run_direct_board.py` 为新硬件配套PS入口；复用相邻hls_markers、hls_geometry的软件依赖及板上编译的libmarker_match.so。此阶段只检查代码和协议，不执行该入口、不加载bitstream。默认只发布点表，`--snapshot-fps 2`才在仍持有lease时读完整图作PC预览；因此预览仍有额外PS读图开销，正常测性能应分别记录开/关预览。

待后续授权上板：检查当前bit/hwh匹配并停旧控制进程，安全加载新bit；冻结图逐项比较候选区域与XYZ；再实测持续周期、PS占用、采集丢帧和快照一致性。目标14–20Hz仅预算，本次布局布线不构成帧率验证。

## 时序报告的适用范围

当前100MHz已约束逻辑的setup/hold通过。整板继承了原compact工程相机路径的限制：328个相机FIFO相关时序单元未被时钟覆盖、部分I/O缺少延时约束，原50MHz时钟定义有覆盖告警；省略按键后原XDC的mode_button三条约束找不到端口。这些不能通过简单屏蔽告警证明采样正确。

新增分支reset由同100MHz域的branch_enable寄存器与原同步resetn相与产生；BD对未附输出复位时钟关联元数据的模块引用给出异步源告警。该输出并非独立时钟域信号。仍须后续上板验收，不将本次正裕量描述为整套传感器接口时序已完全认证。

## 2026-10-27 板测修正与诊断（进行中）

实际ACZ7015 PS参考时钟33.333MHz，PYNQ旧运行时按50MHz估计，不能使用`Clocks.fclk0_mhz=100`推断实际100MHz。内核及IOPLL寄存器确认IOPLL约1GHz，启动使用`Clocks.set_pl_clk(0,div0=5,div1=2)`，核对分频寄存器。此后双目完整帧、格式和溢出检查通过，原图可用。

当前VDMA在门控只送一帧时没有置IOC（包含FrameCntEn模式）；驱动修正为：严格等待921600像素EOF、门控关闭，再清RS请求停机，等待Halted确认且再次检查全部错误位，才提交lease。该过程不对尚在传送的视频帧提前停机；错误位包含bit15 EOLLateErr。板上验证完整帧后状态0x10001，DDR图像正常。

直接reader首个AXI事务报错，尚未通过端到端验收，不能宣称加速有效。新增只读0x40最后AR地址、0x44最后ARLEN、0x48最后RRESP及bit8 RLAST、0x4c累计响应拍数，用于定位。此时不得复用旧点表冒充实时结果。
