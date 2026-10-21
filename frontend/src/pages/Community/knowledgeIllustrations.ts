import type { Reference } from '../../types/community'

const root = '/images/knowledge/'
const scenes = {
  light: { src: root + 'light-v1.webp', label: '棚膜清洁与自然光照', generated: true },
  ventilation: { src: root + 'ventilation-v1.webp', label: '棚顶通风与排湿', generated: true },
  winter: { src: root + 'winter-v1.webp', label: '棚体覆盖与冬季保温', generated: true },
  irrigation: { src: root + 'irrigation-v1.webp', label: '根际滴灌与水分管理', generated: true },
  inspection: { src: root + 'inspection-v1.webp', label: '叶片观察与田间巡查', generated: true },
  seedling: { src: root + 'seedling-v1.webp', label: '穴盘育苗', generated: false },
  tomato: { src: root + 'tomato-v1.webp', label: '番茄果实与成熟管理', generated: false },
  muskmelon: { src: root + 'muskmelon-v1.webp', label: '甜瓜植株与果实管理', generated: false },
  environment: { src: root + 'environment-v1.webp', label: '温室环境监测', generated: false },
  greenhouse: { src: root + 'greenhouse-v1.webp', label: '设施棚体与种植环境', generated: false },
}

// Match the subject before the broad category. Never select by list position:
// sorting, pagination and searching must keep the same illustration for an article.
export function getKnowledgeIllustration(item: Reference) {
  const title = item.title
  const cropScene = item.crops?.length === 1 && item.crops.includes('muskmelon')
    ? scenes.muskmelon : scenes.tomato
  if (item.category === '病害与虫害' || /病害|虫害|症状|病株|潜叶蛾|害螨|蓟马|脐腐/.test(title)) return scenes.inspection
  if (/采收|抢收|成熟|转色|裂果/.test(title)) return cropScene
  if (/棚膜|透光|光照|遮阳|寡照/.test(title)) return scenes.light
  if (/通风|排湿|放风/.test(title)) return scenes.ventilation
  if (/雨雪|保温|防寒|寒潮|低温|覆盖/.test(title)) return scenes.winter
  if (/水肥|供水|水分|灌溉|滴灌|施肥|土壤|排水|排灌|受涝|墒情/.test(title)) return scenes.irrigation
  if (/育苗|定植|缓苗|健康苗|换茬/.test(title)) return scenes.seedling
  if (/整枝|授粉|疏果|绑蔓/.test(title)) return cropScene
  if (/强风|台风|棚体|支架/.test(title)) return scenes.greenhouse
  if (item.category === '水肥与土壤') return scenes.irrigation
  if (item.category === '育苗与定植') return scenes.seedling
  if (item.category === '环境与气象') return scenes.environment
  if (item.category === '整枝与授粉' || item.category === '采收与品质') return cropScene
  return scenes.greenhouse
}

export const knowledgeFallback = scenes.greenhouse
