import SceneIcon from '../components/SceneIcon'
import baseImage from '../assets/images/scene-base.png'

export default function BaseSection() {
  return (
    <section className="scenario-section scenario-section--base">
      <div className="scenario-inner">
        <div className="scenario-title">
          <div className="scenario-leaf">◒</div>
          <div>
            <h2><span>05</span> 区域示范与规模化基地 · 可复制、可推广</h2>
            <p>
              适用于现代农业园区、合作社、家庭农场等规模化种植场景，支持多棚管理、远程查看和数据汇总，助力形成可复制、可推广的数字化种植模式。
            </p>
          </div>
        </div>

        <div className="base-grid">
          <div className="scenario-photo">
            <img src={baseImage} alt="区域规模化设施农业基地" />
          </div>

          <div className="scenario-card"><span><SceneIcon name="users" /></span><strong>多棚统一管理</strong><small>集中查看，统一调度</small></div>
          <div className="scenario-card"><span><SceneIcon name="trend" /></span><strong>数据统计分析</strong><small>形成区域种植画像</small></div>
          <div className="scenario-card"><span><SceneIcon name="settings" /></span><strong>标准化管理</strong><small>助力规模化生产</small></div>

          <div className="map-panel">
            <h3>已在多地开展应用探索</h3>
            <svg viewBox="0 0 430 215">
              <path d="M66 49 123 28l38 19 39-18 52 14 44 42 50 8-10 34-42 11-15 42-50-7-29 25-33-28-53 4-22-34-42-3-7-42Z" fill="#d7eee3" />
              <path d="M94 128Q181 71 308 74M127 146Q210 94 325 119M214 164Q258 119 322 92" fill="none" stroke="#07825f" strokeWidth="3" />
              {[[94,128],[127,146],[214,164],[308,74],[325,119],[322,92]].map(([x,y]) => (
                <g key={`${x}-${y}`}>
                  <circle cx={x} cy={y} r="7" fill="#fff" stroke="#087c5e" strokeWidth="3" />
                  <circle cx={x} cy={y} r="2.5" fill="#087c5e" />
                </g>
              ))}
            </svg>
            <ul>
              <li><b>山东</b> 设施蔬菜基地</li>
              <li><b>江苏</b> 现代农业园区</li>
              <li><b>云南</b> 高原特色种植</li>
              <li><b>四川</b> 乡村振兴示范区</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  )
}
