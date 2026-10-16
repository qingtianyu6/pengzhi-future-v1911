import { useEffect, useState } from 'react'
import type { CropType, GreenhouseInteriorConfig } from './scene/config/types'

const crops: Array<{ id: CropType; name: string }> = [
  { id: 'tomato', name: '番茄' },
  { id: 'cucumber', name: '黄瓜' },
  { id: 'pepper', name: '辣椒' },
  { id: 'strawberry', name: '草莓' },
  { id: 'lettuce', name: '叶菜' },
]

export default function Greenhouse3DConfigDrawer({ config, onClose, onSave }: { config: GreenhouseInteriorConfig; onClose: () => void; onSave: (config: GreenhouseInteriorConfig) => void }) {
  const [draft, setDraft] = useState(config)
  useEffect(() => setDraft(config), [config])

  return <div className="g3d-drawer-mask" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose() }}>
    <aside className="g3d-config-drawer">
      <header><div><small>3D LAYOUT CONFIG</small><h2>大棚三维布局</h2><p>仅保存当前浏览器的 3D 布局，不修改业务数据库。</p></div><button type="button" onClick={onClose}>×</button></header>
      <section className="g3d-config-section"><div><span>主通道宽度</span><strong>{draft.layout.mainAisleWidth.toFixed(1)} m</strong></div><input type="range" min="1" max="2" step="0.1" value={draft.layout.mainAisleWidth} onChange={(event) => setDraft({ ...draft, layout: { ...draft.layout, mainAisleWidth: Number(event.target.value) } })} /></section>
      <div className="g3d-zone-list">{draft.zones.map((zone, index) => <section className="g3d-zone-row" key={zone.id}><b>{zone.id}区</b><select value={zone.crop} onChange={(event) => { const zones = draft.zones.map((item, i) => i === index ? { ...item, crop: event.target.value as CropType } : item); setDraft({ ...draft, zones }) }}>{crops.map((crop) => <option value={crop.id} key={crop.id}>{crop.name}</option>)}</select><div className="g3d-stepper"><button type="button" onClick={() => { const zones = draft.zones.map((item, i) => i === index ? { ...item, bedCount: Math.max(1, item.bedCount - 1) } : item); setDraft({ ...draft, zones }) }}>−</button><span>{zone.bedCount} 垄</span><button type="button" onClick={() => { const zones = draft.zones.map((item, i) => i === index ? { ...item, bedCount: Math.min(8, item.bedCount + 1) } : item); setDraft({ ...draft, zones }) }}>＋</button></div></section>)}</div>
      <p className="g3d-config-tip">布局由参数化引擎实时计算。若垄数超过可用宽度，场景会显示校验提示。</p>
      <footer><button type="button" className="ghost" onClick={onClose}>取消</button><button type="button" className="primary" onClick={() => onSave(draft)}>保存 3D 布局</button></footer>
    </aside>
  </div>
}
