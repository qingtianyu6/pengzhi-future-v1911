import type { ReactNode } from 'react'
import { BarChartOutlined, CloudOutlined, DatabaseOutlined, ExperimentOutlined } from '@ant-design/icons'
import './MarketingVisuals.css'

export function DashboardMockup({ compact = false, title = '智能农业管理平台' }: { compact?: boolean; title?: string }) {
  return <div className={`dashboard-mockup ${compact ? 'compact' : ''}`} aria-label={title}>
    <div className="dashboard-topbar">
      <span className="dashboard-brand-dot"/><strong>棚智未来</strong><em>|</em><span className="dashboard-topbar-title">{title}</span>
      <span className="dashboard-time">2025-09-17 14:26</span><span className="dashboard-avatar"/>
    </div>
    <div className="dashboard-shell">
      <aside>
        <b>▣ 总览</b><span>⌁ 环境监测</span><span>◉ 病害识别</span><span>✓ 农事管理</span><span>✦ 智能决策</span><span>▤ 数据档案</span>
      </aside>
      <section>
        <div className="dashboard-section-head"><strong>温室环境概览</strong><div><span>1号棚 ⌄</span><b>● 设备在线</b></div></div>
        <div className="dashboard-live-title">实时数据</div>
        <div className="dashboard-metrics">
          <div><span className="dashboard-metric-icon temp">♨</span><small>温度</small><b>24.6℃</b><em>温度</em></div>
          <div><span className="dashboard-metric-icon humid">◉</span><small>湿度</small><b>62%</b><em>湿度</em></div>
          <div><span className="dashboard-metric-icon light">☀</span><small>光照</small><b>685 <i>μmol/m²·s</i></b><em>光照</em></div>
        </div>
        <div className="dashboard-chart">
          <div className="dashboard-chart-title"><strong>环境趋势</strong><span><i className="legend green"/>温度(℃) <i className="legend orange"/>湿度(%) <i className="legend blue"/>光照(×100)</span></div>
          <svg viewBox="0 0 560 190" preserveAspectRatio="none" aria-hidden="true">
            <g className="grid"><line x1="42" y1="28" x2="542" y2="28"/><line x1="42" y1="65" x2="542" y2="65"/><line x1="42" y1="102" x2="542" y2="102"/><line x1="42" y1="139" x2="542" y2="139"/><line x1="42" y1="176" x2="542" y2="176"/></g>
            <path className="line green" d="M42 142 C110 142 158 132 206 92 S300 54 352 94 S442 144 542 90"/>
            <path className="line orange" d="M42 128 C115 130 168 118 226 104 S320 112 364 146 S444 162 542 140"/>
            <path className="line blue" d="M42 150 C118 148 170 142 232 126 S342 136 390 122 S472 104 542 112"/>
            <g className="axis"><text x="8" y="32">40</text><text x="8" y="69">30</text><text x="8" y="106">20</text><text x="8" y="143">10</text><text x="16" y="180">0</text><text x="42" y="188">00:00</text><text x="158" y="188">04:00</text><text x="270" y="188">08:00</text><text x="386" y="188">12:00</text><text x="500" y="188">16:00</text></g>
          </svg>
        </div>
        <div className="dashboard-bottom"><div><DatabaseOutlined/><span>今日记录</span></div><div><ExperimentOutlined/><span>风险识别</span></div><div><CloudOutlined/><span>天气影响</span></div></div>
      </section>
    </div>
  </div>
}

export function PhoneMockup() {
  return <div className="phone-mockup" aria-label="移动端管理界面">
    <span className="phone-speaker"/>
    <div className="phone-screen"><strong>棚智未来</strong><div className="phone-stats"><b>24.6℃</b><b>62%</b></div><div className="phone-grid"><i/><i/><i/><i/></div><div className="phone-list"><span/><span/><span/></div></div>
  </div>
}

export function PhotoWithDevices({ src, alt, children }: { src: string; alt: string; children?: ReactNode }) {
  return <div className="photo-device-scene">
    <img src={src} alt={alt}/>
    <div className="photo-scene-gradient"/>
    {children}
  </div>
}

export function DataCard({ icon = 'chart', label, value, unit, className = '' }: { icon?: 'chart'|'database'; label: string; value: string; unit?: string; className?: string }) {
  return <div className={`visual-data-card ${className}`}>
    {icon === 'database' ? <DatabaseOutlined/> : <BarChartOutlined/>}
    <small>{label}</small><strong>{value}<em>{unit}</em></strong><span><i/><i/><i/><i/></span>
  </div>
}

export function MiniLayerStack() {
  return <div className="layer-stack" aria-label="多源数据融合分层架构">
    {[
      ['应用层','智能决策与管理'],['模型层','算法分析与知识融合'],['数据层','多源数据采集与融合'],['感知层','设备采集与边缘处理'],
    ].map(([a,b],i)=><div key={a} className={`layer-stack-${i}`}><strong>{a}</strong><span>{b}</span></div>)}
  </div>
}

export function TrendMiniChart() {
  return <div className="trend-mini-chart"><div className="trend-bars">{[32,42,48,62,76,92].map((h,i)=><i key={i} style={{height:`${h}%`}}/>)}</div><svg viewBox="0 0 300 120" preserveAspectRatio="none"><polyline points="5,94 55,82 105,86 155,58 205,48 295,18"/></svg><b>92%</b><small>识别准确率持续提升</small></div>
}
