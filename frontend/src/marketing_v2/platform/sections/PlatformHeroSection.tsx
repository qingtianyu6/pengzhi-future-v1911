import greenhouse from '../assets/images/greenhouse-wide.png'
import devices from '../assets/images/hero-devices.png'
import { Icon } from '../components/Icons'

const points = [
  { icon: 'leaf' as const, title: '环境看变化', desc: '第一时间知道' },
  { icon: 'sprout' as const, title: '作物有问题', desc: '拍照就能辅助分析' },
  { icon: 'grid' as const, title: '今天干过什么', desc: '系统帮你留下记录' },
]

export default function PlatformHeroSection() {
  return (
    <section className="platform-hero" id="platform-top">
      <img className="platform-hero__bg" src={greenhouse} alt="现代温室" />
      <div className="platform-hero__wash" />
      <img className="platform-hero__devices" src={devices} alt="棚智未来电脑端与手机端" />
      <div className="platform-hero__inner">
        <div className="platform-hero__copy">
          <div className="eyebrow">关于我们 <span /></div>
          <h1>不是多一个农业系统，<br />而是让大棚真正<span>看得见、<br />管得住、有人帮。</span></h1>
          <p>棚智未来面向设施农业日常生产场景，把环境监测、病害识别、农事记录和智能建议放到一个平台里。<br />让种植人员不用反复切换设备和软件，也能快速知道棚里发生了什么、接下来该做什么。</p>
          <div className="hero-points">
            {points.map((item) => <div className="hero-point" key={item.title}><span><Icon name={item.icon} /></span><strong>{item.title}</strong><small>{item.desc}</small></div>)}
          </div>
        </div>
        <div className="hero-handnote">让每一座大棚<br />拥有<span>智慧生长力</span><i /></div>
      </div>
    </section>
  )
}
