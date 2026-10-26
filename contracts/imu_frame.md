# ImuFrame v1

最终 IP 输出为 32-bit AXI4-Stream：每帧固定 16 words / 64 bytes，`TLAST` 仅在 word 15，`TVALID && TREADY` 才推进。阻塞时 `TDATA/TLAST/TVALID` 保持稳定。CPU、文件或网络按 little-endian 序列化每个 word。

原始值是传感器直接读取的有符号 `int16`，未经去偏、滤波、坐标变换。姿态来自同一个序号和时间戳的原始帧。ARM 解算时将整个完整帧写回 IP；不能把解算结果与 IP 此刻的最新采样拼接。IP 采用 shadow/commit 双缓冲，正在输出的一帧不会被后续写入改变。

| Word | 字段 | 编码 |
|---:|---|---|
| 0 | magic | `0x494D5531`（IMU1 标识数值） |
| 1 | version / flags | `[31:16]=1`；bit 0=姿态有效，bit 1=yaw 为相对航向且会漂移，bit 2=本帧采用加速度校正；其余为 0 |
| 2 | sequence | `uint32`，成功完成原始读取时递增，允许回绕 |
| 3 | timestamp_us low | FPGA 64-bit 微秒计数器低 32 位 |
| 4 | timestamp_us high | 高 32 位 |
| 5 | ax / ay | `[15:0]=ax`，`[31:16]=ay`，`int16` |
| 6 | az / temperature | `[15:0]=az`，`[31:16]=temperature`，`int16` |
| 7 | gx / gy | `[15:0]=gx`，`[31:16]=gy`，`int16` |
| 8 | gz / reserved | `[15:0]=gz`，`[31:16]=0` |
| 9 | yaw_deg | IEEE-754 float32，单位度 |
| 10 | pitch_deg | IEEE-754 float32，单位度 |
| 11 | roll_deg | IEEE-754 float32，单位度 |
| 12 | i2c_errors | FPGA I²C 失败累计次数 |
| 13 | dropped_samples | ARM 本次运行检测到的成功采集帧漏读数，低 32 位 |
| 14 | attitude_epoch | 解算重置次数；变化表示姿态参考系重新初始化 |
| 15 | reserved | 0 |

加速度量程 ±4 g，8192 LSB/g；陀螺仪 ±500 °/s，65.5 LSB/(°/s)；温度换算 `raw/340 + 36.53` °C。

姿态沿 MPU6050 芯片标注的右手坐标系，四元数将 sensor 坐标旋转到 world；Euler 采用 `Rz(yaw) Ry(pitch) Rx(roll)`。yaw/roll 在 ±180°，pitch 在 ±90°，接近 pitch ±90° 时 Euler 存在奇异性。JSON 同时保留 `quaternion_wxyz`，便于后续融合。固定安装方向与手部坐标的变换需上板时标定。

`timestamp_us` 在发起 `0x3B` 连续读取时锁存，属于**读取启动时间**，不是 MPU 内部精确采样时刻、UTC 或 ARM 输出时间。未接 INT 引脚，因此包含轮询等待和传感器 DLPF 群延迟；不能声称与相机曝光精确同步。计数器从 PL reset 起算，I²C 故障恢复不会重置它；最终多传感器工程应共享时间基准。

启动校准期间没有有效完整姿态帧，原始数据仍可从采集寄存器读取。I²C 失败清除采集有效标志，直到重新初始化并采到新帧。ARM 检测到错误计数变化或 >20 ms 的时间断点时重新静止校准、递增 epoch。MPU6050 无磁力计，yaw 的长期绝对方向不可观测。

## AXI4-Lite：默认基址 0x43C10000

| Offset | 含义 |
|---:|---|
| `0x00` | ABI 标识 `0x4D505531` |
| `0x04` | bit 0=sample_valid，bit 1=initialized |
| `0x08` | 最新原始采集 sequence |
| `0x0C / 0x10` | 最新原始采集 timestamp low/high |
| `0x14 / 0x18 / 0x1C` | ax/ay/az，符号扩展到 int32 |
| `0x20 / 0x24 / 0x28` | gx/gy/gz，符号扩展到 int32 |
| `0x2C` | temperature，符号扩展到 int32 |
| `0x30` | I²C 错误计数 |
| `0x34` | 传感器配置采样率，500 Hz |
| `0x38 / 0x3C` | 当前 PL 微秒计数 low/high，用 high/low/high 重读避免回绕撕裂 |
| `0x40..0x7C` | 16-word 完整帧 shadow，只写，支持 WSTRB |
| `0x80` | 读 bit 0=packet_busy；写完整 32-bit `1` 提交 shadow |
| `0x84` | 已通过 AXIS 输出的完整帧数 |
| `0x90` | 诊断端口：读 bit 0=busy；写 bit 0=启动、bit 1=写传感器、bits 15:8=寄存器地址、bits 23:16=写入值 |
| `0x94` | 最近一次诊断读取的 byte |
| `0x98` | 完成的诊断命令计数；发起后须等待计数变化并核对 I²C 错误数 |
| `0xC0..0xFC` | 最近提交的 16-word 完整帧，只读，直到下次提交前稳定 |

读取原始帧时在前后重读 sequence/status/error_count，变化则重试。提交时 busy、magic/version/valid 不合法、写只读区或非对齐访问返回 `SLVERR`。AXI 地址与写数据可独立到达。

独立验证 overlay 将 `TREADY` 固定为 1，数据流自动排出，并保留最近完整帧供 MMIO 检查；迁入最终工程时，将 `m_axis` 接到融合/FIFO/DMA。它不会自动将数据发往摄像头或网络。ARM 若遇输出阻塞会保留正在输出的帧，丢弃当前待提交姿态并统计 `packet_backpressure_drops`，不会阻塞传感器采集。

诊断命令在自动采集事务间插入，busy 时拒绝新命令。`diagnose_mpu6050.py` 用于上板核对真实传感器配置，诊断写入可改变传感器状态，不能在正式标定/姿态采集时同时运行。写入后应重新初始化并校准。
