# 硬件待办 · HARDWARE_PENDING

所有项目均未获实体测量验证，软件回执不能代替设备运行证据。

- [ ] 确认 STM32F103C8T6 实物、电源、BOOT0 和 ST-Link / SWD 烧录器。
- [ ] 确认 USB 转 TTL 支持 3.3V 逻辑；核对 Windows COM 编号与驱动。
- [ ] 确认 OLED 是 SSD1306 I2C 128×64、地址 0x3C；核对电压与上拉。
- [ ] 核对 USART1 PA9 TX → TTL RX、PA10 RX ← TTL TX、共地。
- [ ] 核对 PB6 SCL、PB7 SDA 与 OLED 实际接线。
- [ ] 核对 PC13 指示灯是否低电平有效。
- [ ] 核对 PA0 风扇、PA1 水泵、PA2 补光灯的独立驱动输入，默认高电平有效。
- [ ] 确认驱动器接受 3.3V、独立低压电源、共地、感性负载保护；负载禁止直接接 GPIO 供电。
- [ ] 先断开外部负载，保持 GH_OUTPUTS_CONFIRMED=0 构建并烧录；验证串口、LED 和拒绝高风险输出。
- [ ] 实测上电/复位、串口拔出、失联、MCU 卡死和急停时输出关闭。
- [ ] 实测固件8秒水泵限制、12秒冷却、4秒风扇/灯光启停限制。
- [ ] 确认接线后，将 config.h 的 GH_OUTPUTS_CONFIRMED 改为1重新编译与烧录，再使用 -DeviceMode real -PinsVerified。
- [ ] 分别验证风扇、补光灯、水泵；水泵必须有人监督，先用 LED / 假负载测试。
- [ ] 真实 OLED 内容、UART 波特率误差、GPIO 电平、设备动作逐项记录。
- [ ] 如需“实体运行已验证”，另接转速/电流/流量等反馈，增加反馈协议和验收；当前版本始终 physical_verified=false。
