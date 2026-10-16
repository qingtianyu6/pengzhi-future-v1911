import { Empty } from 'antd'
const fields: Record<string, string> = { title: '标题', plan_name: '选择方案', recorded_at: '采集时间', captured_at: '快照时间', temperature: '温度（℃）', air_humidity: '空气湿度（%）', soil_moisture: '土壤湿度（%）', light_intensity: '光照（klx）', co2_concentration: 'CO₂（ppm）', overall_score: '规则风险分', level: '风险等级', status: '状态', rule_version: '规则版本', explanation: '判断依据', rationale: '方案依据', data_source: '数据来源', safety_note: '执行提示' }
export function EvidenceSummary({ value }: { value: unknown }) {
  const rows: Array<{ key: string; title: string; value: string }> = []
  function visit(data: unknown, prefix = '') {
    if (!data || typeof data !== 'object' || Array.isArray(data)) return
    for (const [key, item] of Object.entries(data)) {
      if (fields[key] && item != null && typeof item !== 'object') {
        const text = key.endsWith('_at') ? new Date(String(item)).toLocaleString('zh-CN') : String(item)
        rows.push({ key: prefix + key, title: fields[key], value: text })
      } else if (['latest_sensor_data', 'current_risk', 'risk_event', 'decision_plan'].includes(key)) visit(item, key + '.')
    }
  }
  visit(value)
  return <><div className="evidence-summary">{rows.length ? rows.map(row => <div key={row.key}><span>{row.title}</span><strong>{row.value}</strong></div>) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该环节尚无可用证据" />}</div><details><summary>查看原始记录</summary><pre className="compact-json">{JSON.stringify(value ?? {}, null, 2)}</pre></details></>
}
