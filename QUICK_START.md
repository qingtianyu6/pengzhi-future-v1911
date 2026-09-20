# 快速启动

## 环境要求

- Windows 10/11 64 位
- Python 3.11 或 3.12
- Node.js 20 或更高版本

## 首次安装

在项目根目录打开 PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

## 开发模式

```powershell
.\start_all.ps1
```

访问 `http://127.0.0.1:5173`。启动脚本会检查 5173/8000 端口，旧服务占用端口时会直接提示。

停止：

```powershell
.\stop_all.ps1
```

## 首次使用

1. 在“数据中心”创建大棚和种植批次；
2. 选择 CSV/Excel 导入，或按数据中心给出的 HTTP 示例接入传感器；
3. 在“智能研判”查看环境趋势、未来 1～6 小时预测和风险事件；
4. 在“病害识别”上传番茄叶片图片，查看 Top-3 候选并处理低置信复核；
5. 在“生产闭环”审核建议、生成任务并记录执行反馈；
6. 点击右下角“棚小智”，可选择通用问答或指定大棚对话。

没有环境记录时，系统保持空状态，不生成占位数值。

## 传感器接入

设备上报接口：

```text
POST /api/v1/ingest/sensor-data
```

生产环境建议在 `backend/.env` 配置：

```text
SENSOR_INGEST_KEY=请替换为随机长字符串
```

设备请求头：

```text
X-Sensor-Key: 你的密钥
```

## 生产模式

```powershell
.\start_production.ps1
```

访问 `http://127.0.0.1:8000`。

## 发布前验证

```powershell
.\verify_release.ps1
```
