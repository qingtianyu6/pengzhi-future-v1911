import SectionHeader from '../components/SectionHeader'
import HandNote from '../components/HandNote'
import sensor from '../assets/images/env-sensor.png'
import greenhouse from '../assets/images/greenhouse-wide.png'
import temp from '../assets/icons/temp.png'
import humidity from '../assets/icons/humidity.png'
import light from '../assets/icons/light.png'
import soil from '../assets/icons/soil.png'
import co2 from '../assets/icons/co2.png'

const metrics = [
  [temp, '温度', '实时监测棚内温度变化'],
  [humidity, '湿度', '掌握空气湿度情况'],
  [light, '光照', '分析光照强度与时长'],
  [soil, '土壤', '关注土壤温湿度'],
  [co2, 'CO₂', '监测二氧化碳浓度'],
]

export default function EnvironmentSection() {
  return (
    <section id="environment" className="feature-section feature-section--first">
      <SectionHeader number="01" title="环境监测" subtitle="实时感知，全面掌握" />
      <p className="section-desc">通过多种传感器，对大棚内的温度、湿度、光照、土壤等环境因子进行实时监测，<br/>数据自动上传、自动分析，异常情况及时提醒。</p>
      <HandNote className="section-note note-one">让数据替你时刻守在大棚里</HandNote>
      <div className="environment-grid">
        <div className="sensor-card">
          <img src={greenhouse} className="sensor-card__bg" alt="" />
          <div className="sensor-card__shade" />
          <img src={sensor} className="sensor-card__device" alt="环境监测传感器" />
        </div>
        <div className="metric-list">
          {metrics.map(([icon, title, desc]) => (
            <div className="metric-row" key={title}>
              <div className="metric-icon"><img src={icon} alt="" /></div>
              <div><strong>{title}</strong><span>{desc}</span></div>
            </div>
          ))}
        </div>
        <EnvironmentChart />
      </div>
    </section>
  )
}

function EnvironmentChart() {
  return (
    <div className="chart-card">
      <h4>环境数据实时监测</h4>
      <div className="chart-tabs"><span className="active">温度</span><span>湿度</span><span>光照</span><span>CO₂</span><span>土壤</span></div>
      <div className="chart-wrap">
        <svg viewBox="0 0 520 250" role="img" aria-label="温湿度趋势图">
          <defs>
            <linearGradient id="greenFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3fac7b" stopOpacity=".17"/><stop offset="1" stopColor="#3fac7b" stopOpacity="0"/></linearGradient>
          </defs>
          {[40,90,140,190].map(y => <line key={y} x1="32" y1={y} x2="505" y2={y} stroke="#e5eee9" strokeDasharray="4 5" />)}
          {[85,190,295,400].map(x => <line key={x} x1={x} y1="26" x2={x} y2="212" stroke="#edf3ef" strokeDasharray="4 5" />)}
          <path d="M35 177 C82 171, 105 153, 144 140 S212 104, 256 110 S328 126, 377 138 S444 150, 505 155 L505 212 L35 212 Z" fill="url(#greenFill)" />
          <path d="M35 177 C82 171, 105 153, 144 140 S212 104, 256 110 S328 126, 377 138 S444 150, 505 155" fill="none" stroke="#4ab48a" strokeWidth="3.5" strokeLinecap="round" />
          <path d="M35 113 C83 112, 116 87, 157 89 S224 109, 263 111 S326 87, 366 100 S430 141, 505 111" fill="none" stroke="#f2a43a" strokeWidth="3.5" strokeLinecap="round" />
          <line x1="300" y1="28" x2="300" y2="212" stroke="#8fcbb0" strokeDasharray="5 5" />
          <circle cx="300" cy="112" r="5" fill="#f2a43a" stroke="#fff" strokeWidth="3"/><circle cx="300" cy="119" r="5" fill="#4ab48a" stroke="#fff" strokeWidth="3"/>
          <text x="32" y="236" fill="#8a9891" fontSize="13">00:00</text><text x="150" y="236" fill="#8a9891" fontSize="13">06:00</text><text x="270" y="236" fill="#8a9891" fontSize="13">12:00</text><text x="390" y="236" fill="#8a9891" fontSize="13">18:00</text><text x="468" y="236" fill="#8a9891" fontSize="13">24:00</text>
        </svg>
        <div className="chart-tooltip"><b>12:30</b><span><i className="dot temp"/>温度&nbsp; 24.6℃</span><span><i className="dot humid"/>湿度&nbsp; 62%</span></div>
      </div>
    </div>
  )
}
