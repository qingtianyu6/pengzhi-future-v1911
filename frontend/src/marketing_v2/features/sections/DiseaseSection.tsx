import { useMemo, useState } from 'react'
import SectionHeader from '../components/SectionHeader'
import HandNote from '../components/HandNote'
import phone from '../assets/images/disease-phone.png'
import powdery from '../assets/images/disease-powdery.png'
import downy from '../assets/images/disease-downy.png'
import gray from '../assets/images/disease-gray.png'
import anthracnose from '../assets/images/disease-anthracnose.png'

const diseaseList = [
  { key: 'powdery', name: '白粉病', image: powdery, confidence: 95, advice: ['及时清除病叶', '保持通风降湿', '合理控制种植密度'] },
  { key: 'downy', name: '霜霉病', image: downy, confidence: 93, advice: ['降低棚内湿度', '改善通风条件', '重点巡查叶片背面'] },
  { key: 'gray', name: '灰霉病', image: gray, confidence: 94, advice: ['病叶及时隔离', '减少叶面结露', '加强棚内空气流动'] },
  { key: 'anthracnose', name: '炭疽病', image: anthracnose, confidence: 92, advice: ['及时摘除病叶', '加强通风降湿', '请农技人员复核处置'] },
]

export default function DiseaseSection() {
  const [active, setActive] = useState('anthracnose')
  const current = useMemo(() => diseaseList.find(d => d.key === active)!, [active])

  return (
    <section id="disease" className="feature-section">
      <SectionHeader number="02" title="病害识别" subtitle="拍照识别，防患于未然" />
      <p className="section-desc">当前模型用于番茄叶片，覆盖健康、早疫病、晚疫病、叶霉病、斑枯病和番茄黄化曲叶病毒病。<br/>模型仍在评估中，识别结果需人工复核；下方图片为病害巡检场景示意。</p>
      <HandNote className="section-note note-two">拍一张照片，<br/>让专业知识来到你身边</HandNote>
      <div className="disease-grid">
        <div className="phone-card">
          <div className="phone-card__blur" />
          <img src={phone} alt="手机识别病害叶片" />
        </div>
        <div className="result-card">
          <h4>病害巡检示意</h4>
          <div className="result-main">
            <img src={current.image} alt={current.name} />
            <div className="result-copy">
              <strong>{current.name}</strong>
              <p>场景示意，非模型输出</p>
              <span className="risk-tag">高风险</span>
              <h5>防治建议</h5>
              <ul>{current.advice.map(a => <li key={a}>{a}</li>)}</ul>
            </div>
          </div>
        </div>
        <div className="disease-gallery">
          <h4>病害症状示意</h4>
          <div className="disease-thumbs">
            {diseaseList.map(item => (
              <button key={item.key} onClick={() => setActive(item.key)} className={item.key === active ? 'active' : ''}>
                <span><img src={item.image} alt={item.name}/></span><b>{item.name}</b>
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
