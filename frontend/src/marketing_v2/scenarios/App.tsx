import Header from './components/Header'
import HeroSection from './sections/HeroSection'
import ScenarioSection from './sections/ScenarioSection'
import BaseSection from './sections/BaseSection'
import BottomBanner from './sections/BottomBanner'
import tomato from './assets/images/scene-tomato.png'
import strawberry from './assets/images/scene-strawberry.png'
import flower from './assets/images/scene-flower.png'
import seedling from './assets/images/scene-seedling.png'
import './styles.css'

const scenes = [
  {
    no: '01',
    title: '蔬菜种植大棚 · 精准管理，稳定高产',
    desc: '适用于番茄、黄瓜、辣椒、茄子等常见蔬菜种植，实时监测棚内环境，识别病害风险，提供农事建议，帮助种植户实现精细化管理。',
    image: tomato,
    imageAlt: '现代温室中的番茄种植场景',
    note: '让每一棵菜\n都长得更好',
    cards: [
      { icon: 'activity', title: '环境监测', desc: '掌握温湿度、光照、CO₂等关键环境因子' },
      { icon: 'camera', title: '病害识别', desc: '早发现、早干预，降低病害损失' },
      { icon: 'clipboard', title: '农事管理', desc: '浇水、施肥、打药、巡棚全流程记录' },
    ],
    benefits: ['产量提升 10%～30%', '病害损失降低 20%～40%', '管理效率提升 50%以上'],
  },
  {
    no: '02',
    title: '水果种植大棚 · 品质提升，价值更高',
    desc: '适用于草莓、葡萄、樱桃、蓝莓等高附加值水果种植，帮助种植户更好地控制生长环境、提升果实品质与商品率，打造优质品牌。',
    image: strawberry,
    imageAlt: '现代温室中的草莓种植场景',
    note: '好环境，\n结出好果实',
    cards: [
      { icon: 'sprout', title: '生长监测', desc: '关注关键生育期环境变化' },
      { icon: 'camera', title: '品质管理', desc: '通过数据优化果品品质' },
      { icon: 'shield', title: '风险预警', desc: '异常情况及时提醒' },
    ],
    benefits: ['优质果率提升 15%～35%', '商品价值提升 20%～50%', '品牌竞争力增强'],
  },
  {
    no: '03',
    title: '花卉种植大棚 · 环境可控，花开更稳',
    desc: '适用于玫瑰、百合、菊花、蝴蝶兰等花卉种植，精准控制温湿度、光照等环境条件，为花卉高品质生长提供稳定的环境支持。',
    image: flower,
    imageAlt: '现代温室中的花卉种植场景',
    note: '让每一朵花\n都按时绽放',
    cards: [
      { icon: 'sliders', title: '环境调控', desc: '营造适宜的生长环境' },
      { icon: 'clipboard', title: '生长记录', desc: '记录不同生长阶段数据' },
      { icon: 'pin', title: '智能建议', desc: '提供温湿、通风、遮阴等管理建议' },
    ],
    benefits: ['花卉品质提升 20%～40%', '生产成本降低 15%～30%', '出花稳定性增强'],
  },
  {
    no: '04',
    title: '育苗与种苗繁育 · 健康种苗，打好基础',
    desc: '适用于蔬菜育苗、花卉育苗及特色作物种苗繁育，帮助控制育苗环境，提高出苗率与种苗质量，为后续种植提供健康、整齐的种苗。',
    image: seedling,
    imageAlt: '现代温室中的育苗与种苗繁育场景',
    note: '好种苗，\n是丰收的第一步',
    cards: [
      { icon: 'camera', title: '环境精细控制', desc: '保证温湿度稳定' },
      { icon: 'activity', title: '生长状态监测', desc: '及时发现异常' },
      { icon: 'clipboard', title: '数据记录', desc: '形成可追溯的育苗档案' },
    ],
    benefits: ['出苗率提升 10%～30%', '种苗质量提升 20%～40%', '育苗成本降低'],
  },
]

export default function App() {
  return (
    <div className="pz-scenarios-v2 site-shell">
      <Header />
      <main>
        <HeroSection />
        {scenes.map((scene) => <ScenarioSection key={scene.no} {...scene} />)}
        <BaseSection />
        <BottomBanner />
      </main>
    </div>
  )
}
