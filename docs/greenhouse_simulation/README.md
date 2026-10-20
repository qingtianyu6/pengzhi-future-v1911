# 棚智自治 · AI 温室模拟调控

这是 iCAN 展示用软件仿真系统。所有环境输入 source=simulation；示例场景、目标、动态模型未经实棚标定，不是生产标准。规则模式明确属于阈值控制，预测优化使用本地动态模型与动作搜索，不调用大模型。

## 运行

在原项目根目录 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_greenhouse_demo.ps1
```

打开 5180 端口的棚智自治游客页，无需 STM32。独立使用 `.run/greenhouse/demo.db`，不改动原业务数据库、账号、环境变量文件。原 `start_all.ps1` 保持原样，仍可在 5173 的智能农艺分组进入棚智自治。

选择六种场景之一（也可命名保存自定义场景） → 调整五项输入/目标 → 选择规则或预测优化 → 启动 → 查看命令、回执与变化曲线。暂停会发送 STOP，重置仅重置当前模拟状态并保留日志。急停锁定后必须重置才能再次执行。手动控制同样走后端和设备协议。修改参数只改变草稿，提交时由后端校验、停止旧动作、重新计算。目标、输入都支持输入框，输入另有滑块。

```powershell
# 核心测试、类型检查、生产构建、固件构建
powershell -ExecutionPolicy Bypass -File .\scripts\test_greenhouse.ps1
# 全部原后端回归测试
powershell -ExecutionPolicy Bypass -File .\scripts\test_greenhouse.ps1 -AllBackend
# 浏览器验证（先启动演示；需 requirements-greenhouse-dev.txt）
backend\.venv\Scripts\python.exe backend\scripts\check_greenhouse_browser.py
# 停止本模块启动的服务；固件失联保护仍独立执行
powershell -ExecutionPolicy Bypass -File .\scripts\stop_greenhouse_demo.ps1
```

依赖：原后端 requirements.txt 新增 pyserial==3.5。测试/编译工具单列 requirements-greenhouse-dev.txt（Playwright、Zig），不作为线上依赖。开发机已安装。缺少环境时脚本创建 venv、安装原依赖和 npm ci；普通已配置项目无需零碎命令。

## 架构及隔离

React 现有 AppLayout/Ant Design → FastAPI `/api/greenhouse-demo` 或 `/api/greenhouse-control` → Runtime → DeviceLink → MockSTM32 或本机 HTTP 桥 → pyserial → USART1 → GPIO / OLED。

- 模拟状态和历史表 `greenhouse_simulation_events` 与 SensorData 隔离，使用已有 Base.metadata.create_all 增量建表，不修改旧表或清空数据。
- 公开 demo 每个浏览器标签拥有随机会话，只能创建 MOCK，与环境变量 REAL 无关；不提供自然语言执行入口。
- 登录 control 复用 business_access：写入要求 admin/agronomist，状态与日志按用户和组织隔离。单个真实控制器仅允许一个会话持有。重启后模型状态归初始，数据库保留审计，可通过 records 接口查询会话记录。
- 不接入原有预测器：原有预测面向生产历史时序，不具备本模块执行器动态模型及训练范围保证；直接复用会产生不适用预测。
- 一个后端进程、一个 worker 运行。设备状态共享是进程内的；不要启用多 worker 或热重载控制实体硬件。
- 后台每2秒推进一次仿真，不依赖前端推进；页面每2秒拉取状态，离开15秒后自动停机。时间步2秒，模拟时钟与墙钟近似一致，不提供加速实体控制。
- 最近300个曲线点、100条页面事件、200条收发记录有界保存；审计事件入库。演示数据库日志可增长，长期部署需另加留存策略。

## 模型与控制

`domain.py` 的 ModelConfig 集中配置。通风与自然交换对室外温湿度产生一阶趋近，土温与空气耦合，灌溉增加土壤含水率、蒸发减少含水率，补光增加光照与小量热源。光照采用指数响应，其余显式小步积分；每步≤10秒且全部变量钳制在校验范围。它不能表示真实温室的全部物理过程。

规则模式对温湿度、含水率、光照使用独立滞回带。预测模式枚举最多8种风扇/泵/灯动作，对24秒时域逐2秒模拟，并经过与运行时一致的设备安全限制；以归一化偏差平方、启停和能耗代理代价选择。LED 是指示输出，不参与优化。目标中的土温通过空气耦合间接影响，无法保证所有目标可达（无加热/遮阳设备）。

对比实验在相同初值、目标、固定种子生成的完全相同扰动序列下分别运行两策略，记录偏差、步数、开启秒数、启停次数、能耗代理和灌溉秒数。页面如实呈现，可能某些指标更差。能耗代理不是电表测量或 kWh。模型系数、种子、步数、扰动和轨迹由 experiment API 返回。

## 状态证据

计划执行 → 命令已发送 → 虚拟确认 / STM32 GPIO 确认；失败时反馈未知。真实 ACK 仅确认解析及软件 GPIO 设置，始终 `physical_verified=false`。没有转速、电流、流量反馈，不能证明负载运转。OLED 的 mock 内容明确标识虚拟显示。

## 协议 V1

ASCII 8N1、默认115200，LF 结尾，最大128字节（含换行）。`*HH` 为星号前全部 ASCII 字节的 XOR 两位十六进制，不含星号与 LF。

```text
V1,<id>,ENV,<air_t*10>,<rh*10>,<soil_t*10>,<moisture*10>,<lux>*HH\n
V1,<id>,SET,<mask>,<lease_ms>,<manual>*HH\n
V1,<id>,STOP*HH\n
V1,<id>,PING*HH\n
V1,<id>,ACK,<request_type>,<current_mask>*HH\n
V1,<id>,ERR,<code>*HH\n
```

id 为1..2147483647；mask bit0=风扇、bit1=水泵、bit2=补光灯、bit3=LED。SET 租约100..5000ms，服务使用4000ms；manual=1 表示手动接管。ENV 只供显示，PING/ENV 不续执行器租约；只有新编号 SET 才续约。最近8个编号去重，相同编号不同内容返回5；相同内容返回当前输出确认，不重新执行、不延长水泵时间/租约。旧编号不应长期重放。后端单命令失败最多重试一次，复用编号；ACK 核对编号和类型。

错误：1未知命令，2参数/范围无效，3执行器引脚未确认，4启停/水泵安全限制，5编号冲突。损坏/超长/非ASCII帧丢弃，不执行；发送方超时可重试。固件字节间超时100ms；桥接等待约800ms，损坏/无关回执忽略，超时关闭句柄，下次重开 COM。日志记录 TX/RX/ERROR。

## 真实串口与 WSL

先完成 HARDWARE_TODO。集中配置 `scripts/greenhouse.config.ps1` 的端口与波特率。

```powershell
# 仅开启 Windows 串口桥（默认监听127.0.0.1:8766）
powershell -ExecutionPolicy Bypass -File .\scripts\start_serial_bridge.ps1
# 实体接线确认且重新烧录已解锁固件后
powershell -ExecutionPolicy Bypass -File .\scripts\start_greenhouse_demo.ps1 -DeviceMode real -PinsVerified
```

桥只在本机监听，无 CORS，所有接口要求随机 Bearer 令牌。令牌保存在 `.run/greenhouse/bridge-token.xml`，由 Windows DPAPI 按当前用户加密；不打印、不写入仓库。Windows COM 由一个桥接进程独占，线程锁串行化请求，串口错误后关闭并自动重开。不要再使用串口监视器抢占同一 COM。游客页永远 MOCK，真实模式需在该演示后端注册/登录。

已有服务可通过环境变量选择：GREENHOUSE_DEVICE_MODE=mock/real；REAL 额外要求 GREENHOUSE_REAL_ENABLED=YES_PINS_VERIFIED、GREENHOUSE_BRIDGE_TOKEN、GREENHOUSE_BRIDGE_URL。桥的 GREENHOUSE_SERIAL_PORT、GREENHOUSE_SERIAL_BAUD 可配置。环境变量切换后重启进程。

推荐所有硬件演示直接用 Windows Python。WSL 若运行后端，桥继续在 Windows 运行；采用 Windows11 WSL 镜像网络的 localhost 转发，通过127.0.0.1:8766访问，不依赖 USB 透传。默认 NAT 下 WSL→Windows localhost 可能不通，请改用 Windows 后端一键命令，或由用户配置 mirrored networking；不对局域网开放无保护桥接端口。此处未验证本机 WSL 网络。

## 固件与接线假设

固件直接使用 STM32F103 寄存器，不依赖未安装的 HAL/CMSIS；内部 HSI 8MHz，Cortex-M3、64KB Flash/20KB RAM 链接布局。USART1 PA9 TX/PA10 RX；SSD1306 I2C PB6 SCL/PB7 SDA、0x3C、128×64；PC13 低电平 LED；PA0/PA1/PA2 分别风扇/泵/灯驱动信号，高电平有效。全部都是待确认的接线假设。

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-greenhouse-dev.txt
backend\.venv\Scripts\python.exe firmware\greenhouse_stm32\build.py
```

优先 arm-none-eabi-gcc，否则 Zig 0.13 的 Clang/LLD 实际交叉编译；输出 `firmware/greenhouse_stm32/build/greenhouse.elf` 和 `.bin`。使用 STM32CubeProgrammer + ST-Link 在0x08000000烧录（用户实物操作，未执行）。先烧录锁定版，仅验证 UART、OLED 和 LED；确认输出引脚及驱动后再修改 config.h 的 GH_OUTPUTS_CONFIRMED=1 构建、烧录。

固件安全：上电关闭、帧校验、参数范围、串口接收中断有界缓冲、通信租约关闭全部输出、水泵最大8秒和12秒冷却、风扇灯光最小间隔4秒、STOP 强制关闭、独立硬件看门狗、RAM 中16条输出日志。独立看门狗标称约2秒，真实时限依赖 LSI 容差须实测。OLED 缺失 ACK 迅速放弃，不阻塞其他模块。物理驱动需3.3V兼容的外部模块，低压独立供电、共地和感性负载保护。禁止 GPIO 直接供电风扇/水泵，禁止无人监督灌溉。

芯片引脚/寄存器依据：[ST STM32F103C8 官方资料](https://www.st.com/en/microcontrollers-microprocessors/stm32f103c8)、[官方数据手册](https://www.st.com/resource/en/datasheet/stm32f103c8.pdf)；串口依据：[pySerial API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html)；交叉编译工具：[Zig 平台支持](https://ziglang.org/learn/platform-support/)。

## 测试和故障排查

实际结果见 TEST_RESULTS.md。HARDWARE_PENDING 列表见 HARDWARE_TODO.md。

- “未连接”：未发送过命令也属正常；启动/单次计算建立协议确认。
- 页面草稿与当前值不同：只有提交后才改变后端，运行中实际值继续演化。
- 失败/超时：可通过“恢复连接”修复 MOCK，再手动启动，不会自动恢复执行器。
- ERR 3：锁定固件正确拒绝了高风险输出，先完成引脚和驱动确认。
- ERR 4：水泵冷却或启停保护，等待限制结束；急停不受最小间隔限制。
- 端口占用：不终止未知进程，修改配置或使用对应 stop 脚本。
- 独立模拟数据不在原生产历史中：设计如此；仅本模块曲线/审计保存。
- 当前不包含传感器采集、实体动作验证、实棚标定、云端远程控制或自然语言设备执行。
