import { useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'
import type { SensorReading } from '../../types/sensor'
import type { EnvironmentPrediction } from '../../types/prediction'
import type { WarningEvent } from '../../types/warning'
import { buildTimeline, type MetricKey } from './timeline'

echarts.use([LineChart, GridComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent, CanvasRenderer])

export default function UnifiedEnvironmentChart({ history, prediction, metric, hours, horizon, now, warning }: {
  history: SensorReading[]; prediction: EnvironmentPrediction | null; metric: MetricKey; hours: number; horizon: number; now: number; warning: WarningEvent | null
}) {
  const host = useRef<HTMLDivElement>(null)
  const timeline = useMemo(() => buildTimeline(history, prediction, metric, now, hours, horizon), [history, prediction, metric, now, hours, horizon])
  useEffect(() => {
    if (!host.current) return
    const chart = echarts.init(host.current)
    const option: EChartsCoreOption = {
      textStyle: { fontFamily: "'Noto Sans SC', 'Microsoft YaHei', sans-serif", fontSize: 13 },
      animationDuration: 300,
      grid: { left: 12, right: 22, top: 46, bottom: 34, containLabel: true },
      tooltip: { trigger: 'axis', renderMode: 'richText', backgroundColor: '#fffefa', borderColor: '#dce2d4', textStyle: { color: '#244b3c', fontSize: 13 } },
      xAxis: { type: 'time', min: timeline.start, max: timeline.end, splitNumber: 7, axisLine: { lineStyle: { color: '#b7c4b2' } }, axisTick: { show: false }, axisLabel: { color: '#7a8975', hideOverlap: true, formatter: (v: number) => new Date(v).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }) }, splitLine: { show: true, lineStyle: { color: '#e5e8de' } } },
      yAxis: { type: 'value', scale: true, name: `${timeline.metric.short} / ${timeline.metric.unit}`, nameTextStyle: { color: '#6a7e68' }, axisLabel: { color: '#7a8975' }, splitLine: { lineStyle: { color: '#e1e6d9' } } },
      series: [
        { name: '实测数据', type: 'line', data: timeline.measured, connectNulls: false, showSymbol: false, lineStyle: { color: '#184e3d', width: 2.3 }, itemStyle: { color: '#184e3d' },
          markLine: { silent: true, symbol: 'none', data: [{ xAxis: now, name: '现在' }], lineStyle: { color: '#749380', type: 'dashed' }, label: { formatter: '现在', position: 'end', color: '#2b5741' } },
          markArea: { silent: true, itemStyle: { color: '#dbe9d41c' }, data: [[{ xAxis: now }, { xAxis: timeline.end }]] } },
        { name: '预测下界', type: 'line', stack: 'range', stackStrategy: 'all', data: timeline.lower, symbol: 'none', connectNulls: false, lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 }, tooltip: { show: false }, emphasis: { disabled: true } },
        { name: '预测区间', type: 'line', stack: 'range', stackStrategy: 'all', data: timeline.span, symbol: 'none', connectNulls: false, lineStyle: { opacity: 0 }, areaStyle: { color: '#a9d2ad', opacity: .26 }, tooltip: { show: false }, emphasis: { disabled: true } },
        { name: '预测数据', type: 'line', data: timeline.forecast, showSymbol: false, connectNulls: false, lineStyle: { color: '#2c9568', width: 2, type: 'dashed' }, itemStyle: { color: '#2c9568' } },
      ],
    }
    chart.setOption(option)
    const resize = new ResizeObserver(() => chart.resize()); resize.observe(host.current)
    return () => { resize.disconnect(); chart.dispose() }
  }, [timeline, now])
  const eventTime = warning ? Date.parse(warning.last_triggered_at) : NaN
  const eventVisible = Number.isFinite(eventTime) && eventTime >= timeline.start && eventTime <= now
  return <>
    <div className="env-chart-region" ref={host} role="img" aria-label={`${timeline.metric.label}历史实测与未来预测曲线`} data-measured={timeline.measured.filter(p => p[1] !== null).length} data-forecast={timeline.forecast.filter(p => p[0] > now && p[1] !== null).length} data-interval={timeline.intervalAvailable} />
    {eventVisible && <div className="env-event-axis"><span style={{ left: `clamp(0px, ${(eventTime - timeline.start) / (timeline.end - timeline.start) * 100}%, calc(100% - 130px))` }} title={warning?.title}><i />预警事件 · {new Date(eventTime).toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit'})}</span></div>}
    <p className="env-chart-note">{timeline.stale ? '最近实测已过期，未将历史记录延伸为当前值。 ' : '实线为实际采样，虚线为预测。 '}{!timeline.predictionAvailable ? '当前指标暂无可用的未来预测。' : `${prediction?.generated_at ? `预测生成于 ${new Date(prediction.generated_at).toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit'})}。` : ''}${timeline.intervalAvailable ? '浅色范围使用接口返回的预测上下界。' : '本次未提供预测区间。'}`}</p>
  </>
}
