# 实施完成状态

P0—P10 核心软件工作已完成：原项目集成、仿真后端、两种自动策略、统一协议、虚拟STM32、控制台、Windows串口桥、独立固件工程、仿真实验、测试、脚本和文档。

实际验证见 TEST_RESULTS.md；实体事项全部列入 HARDWARE_TODO.md。

原项目已有未提交改动已保留，没有删除原项目、重置Git、清空业务数据库、改写.env或推送代码。一键演示使用独立 `.run/greenhouse/demo.db`。

启动：`powershell -ExecutionPolicy Bypass -File .\scripts\start_greenhouse_demo.ps1`

测试：`powershell -ExecutionPolicy Bypass -File .\scripts\test_greenhouse.ps1`

后续仅需实体准备与验证。默认mock，固件高风险输出默认锁定。真实串口、屏幕和设备动作没有宣称通过。
