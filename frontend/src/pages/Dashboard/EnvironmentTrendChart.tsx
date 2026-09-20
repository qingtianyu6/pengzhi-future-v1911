import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { SensorReading } from '../../types/sensor'

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

export function EnvironmentTrendChart({ data }: { data: SensorReading[] }) {
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartRef.current) return
    const chart = echarts.init(chartRef.current)
    chart.setOption({
      animationDuration: 850,
      color: ['#f27b18', '#2f7ff7', '#149666'],
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255,255,255,.98)',
        borderColor: '#dfe8e4',
        borderWidth: 1,
        textStyle: { color: '#27463c', fontSize: 11 },
        extraCssText: 'box-shadow:0 10px 28px rgba(25,67,53,.12);border-radius:10px;',
        padding: [10, 12],
      },
      legend: {
        data: ['温度 (℃)', '湿度 (%)', '土壤湿度 (%)'],
        right: 14,
        top: 2,
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
        itemGap: 22,
        textStyle: { color: '#71847d', fontSize: 10 },
      },
      grid: { left: 4, right: 6, bottom: 2, top: 42, containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: data.map((item) => new Date(item.recorded_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })),
        axisLine: { lineStyle: { color: '#d7e1dd' } },
        axisTick: { show: false },
        axisLabel: { color: '#7c8e87', fontSize: 9, margin: 10, interval: Math.max(0, Math.floor(data.length / 8) - 1) },
      },
      yAxis: [
        {
          type: 'value', name: '温度 (℃)', nameGap: 14, nameTextStyle: { color: '#83948e', fontSize: 9, align: 'left' },
          axisLabel: { color: '#7e8f89', fontSize: 9 }, axisLine: { show: false }, axisTick: { show: false },
          splitLine: { lineStyle: { color: '#e7ece9', type: 'solid' } }, min: 'dataMin',
        },
        {
          type: 'value', name: '湿度 / 土壤湿度 (%)', nameGap: 14, nameTextStyle: { color: '#83948e', fontSize: 9, align: 'right' },
          axisLabel: { color: '#7e8f89', fontSize: 9 }, axisLine: { show: false }, axisTick: { show: false },
          splitLine: { show: false }, min: 0, max: 100,
        },
      ],
      series: [
        { name: '温度 (℃)', type: 'line', smooth: true, showSymbol: true, symbol: 'circle', symbolSize: 4, lineStyle: { width: 2.2 }, itemStyle: { borderWidth: 1.5, borderColor: '#fff' }, data: data.map((item) => item.temperature) },
        { name: '湿度 (%)', type: 'line', smooth: true, showSymbol: true, symbol: 'circle', symbolSize: 4, yAxisIndex: 1, lineStyle: { width: 2.1 }, itemStyle: { borderWidth: 1.5, borderColor: '#fff' }, data: data.map((item) => item.air_humidity) },
        { name: '土壤湿度 (%)', type: 'line', smooth: true, showSymbol: true, symbol: 'circle', symbolSize: 4, yAxisIndex: 1, lineStyle: { width: 2.1 }, itemStyle: { borderWidth: 1.5, borderColor: '#fff' }, data: data.map((item) => item.soil_moisture) },
      ],
    })
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(chartRef.current)
    return () => { observer.disconnect(); chart.dispose() }
  }, [data])

  return <div ref={chartRef} className="environment-chart exact-environment-chart" aria-label="最近24小时温湿度与土壤湿度趋势图" />
}
