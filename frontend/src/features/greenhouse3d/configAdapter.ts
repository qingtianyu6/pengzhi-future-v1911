import type { Greenhouse } from '../../types/greenhouse'
import { isGuestMode } from '../../api/guestMode'
import type { GreenhouseInteriorConfig, CropType } from './scene/config/types'
import { configA } from './scene/config/greenhouseConfig'

const STORAGE_PREFIX = 'pengzhi_3d_layout_'

function layoutStorage() {
  return isGuestMode() ? sessionStorage : localStorage
}

function cloneDefault(greenhouseId: string): GreenhouseInteriorConfig {
  return {
    ...configA,
    greenhouseId,
    layout: { ...configA.layout },
    zones: configA.zones.map((zone) => ({ ...zone })),
    devices: { ...configA.devices },
  }
}

export function cropFromGreenhouse(greenhouse: Greenhouse): CropType | null {
  if (greenhouse.active_batch?.crop_type === 'tomato') return 'tomato'
  const variety = greenhouse.active_batch?.variety ?? ''
  if (/番茄|西红柿/.test(variety)) return 'tomato'
  if (/黄瓜/.test(variety)) return 'cucumber'
  if (/辣椒|甜椒/.test(variety)) return 'pepper'
  if (/草莓/.test(variety)) return 'strawberry'
  if (/生菜|叶菜|菠菜|油菜/.test(variety)) return 'lettuce'
  return null
}

export function buildGreenhouse3DConfig(greenhouse: Greenhouse): GreenhouseInteriorConfig {
  const base = cloneDefault(greenhouse.code || `GH-${greenhouse.id}`)
  const crop = cropFromGreenhouse(greenhouse)
  if (crop) base.zones = base.zones.map((zone) => ({ ...zone, crop }))
  return base
}

export function loadGreenhouse3DConfig(greenhouse: Greenhouse): GreenhouseInteriorConfig {
  const fallback = buildGreenhouse3DConfig(greenhouse)
  try {
    const raw = layoutStorage().getItem(`${STORAGE_PREFIX}${greenhouse.id}`)
    if (!raw) return fallback
    const parsed = JSON.parse(raw) as GreenhouseInteriorConfig
    if (!parsed.layout || !Array.isArray(parsed.zones) || parsed.zones.length !== 4) return fallback
    return { ...parsed, greenhouseId: greenhouse.code || `GH-${greenhouse.id}` }
  } catch {
    return fallback
  }
}

export function saveGreenhouse3DConfig(greenhouseId: number, config: GreenhouseInteriorConfig) {
  layoutStorage().setItem(`${STORAGE_PREFIX}${greenhouseId}`, JSON.stringify(config))
}
