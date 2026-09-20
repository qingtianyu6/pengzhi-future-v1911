import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'
import type { EnvironmentPrediction } from '../../types/prediction'

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

export function EnvironmentForecastChart({ data }: { data: EnvironmentPrediction }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    const times = [...data.history.map((point) => point.timestamp), ...data.predictions.map((point) => point.forecast_time)]
      .map((value) => new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', hour12: false }))
    const historyLength = data.history.length
    const emptyPrediction = Array(data.predictions.length).fill(null)
    const emptyHistory = Array(Math.max(0, historyLength - 1)).fill(null)
    const lastHistory = data.history.at(-1)
    const option: EChartsCoreOption = {
      color: ['#168464', '#3d82c4', '#f0a33a', '#7357b5', '#e8a65c', '#a8bfd9'],
      tooltip: { trigger: 'axis' }, legend: { top: 0 },
      grid: { left: 20, right: 34, top: 52, bottom: 34, containLabel: true },
      xAxis: { type: 'category', boundaryGap: false, data: times, axisLabel: { hideOverlap: true } },
      yAxis: [{ type: 'value', name: '℃', scale: true }, { type: 'value', name: '%RH', min: 0, max: 100 }],
      series: [
        { name: '历史温度', type: 'line', showSymbol: false, data: [...data.history.map((point) => point.temperature_c), ...emptyPrediction], lineStyle: { width: 2 } },
        { name: '历史湿度', type: 'line', yAxisIndex: 1, showSymbol: false, data: [...data.history.map((point) => point.air_humidity_pct), ...emptyPrediction], lineStyle: { width: 2 } },
        { name: '预测温度', type: 'line', showSymbol: true, symbolSize: 5, data: [...emptyHistory, lastHistory?.temperature_c ?? null, ...data.predictions.map((point) => point.temperature_c)], lineStyle: { type: 'dashed', width: 2 }, markLine: { silent: true, symbol: 'none', label: { formatter: '预测起点' }, data: [{ xAxis: Math.max(0, historyLength - 1) }] } },
        { name: '预测湿度', type: 'line', yAxisIndex: 1, showSymbol: true, symbolSize: 5, data: [...emptyHistory, lastHistory?.air_humidity_pct ?? null, ...data.predictions.map((point) => point.air_humidity_pct)], lineStyle: { type: 'dashed', width: 2 } },
        { name: '温度90%下界', type: 'line', showSymbol: false, data: [...Array(historyLength).fill(null), ...data.predictions.map((point) => point.lower_bounds.air_temperature_c ?? null)], lineStyle: { type: 'dotted', width: 1, opacity: 0.7 } },
        { name: '温度90%上界', type: 'line', showSymbol: false, data: [...Array(historyLength).fill(null), ...data.predictions.map((point) => point.upper_bounds.air_temperature_c ?? null)], lineStyle: { type: 'dotted', width: 1, opacity: 0.7 } },
        { name: '湿度90%下界', type: 'line', yAxisIndex: 1, showSymbol: false, data: [...Array(historyLength).fill(null), ...data.predictions.map((point) => point.lower_bounds.air_humidity_pct ?? null)], lineStyle: { type: 'dotted', width: 1, opacity: 0.55 } },
        { name: '湿度90%上界', type: 'line', yAxisIndex: 1, showSymbol: false, data: [...Array(historyLength).fill(null), ...data.predictions.map((point) => point.upper_bounds.air_humidity_pct ?? null)], lineStyle: { type: 'dotted', width: 1, opacity: 0.55 } },
      ],
    }
    chart.setOption(option)
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(ref.current)
    return () => { observer.disconnect(); chart.dispose() }
  }, [data])

  return <div ref={ref} className="forecast-chart" aria-label="最近24小时历史与未来环境预测曲线" />
}
