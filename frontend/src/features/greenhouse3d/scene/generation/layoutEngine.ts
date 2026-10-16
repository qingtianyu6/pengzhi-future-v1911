import type { BedLayout, Collider, GreenhouseInteriorConfig, InteriorLayout, ZoneId, ZoneLayout } from '../config/types'
import { generateBeds } from './bedGenerator'
import { generateDevices } from './deviceGenerator'

const L = 32
const W = 18

export function generateInteriorLayout(config: GreenhouseInteriorConfig): InteriorLayout {
  const aisleHalfWidth = config.layout.mainAisleWidth / 2
  const edge = config.layout.edgeMargin
  const bounds: Record<ZoneId, [[number, number], [number, number]]> = {
    A: [[-L / 2 + edge, -0.45], [-W / 2 + edge, -aisleHalfWidth - 0.28]],
    B: [[-L / 2 + edge, -0.45], [aisleHalfWidth + 0.28, W / 2 - edge]],
    C: [[0.45, L / 2 - edge], [-W / 2 + edge, -aisleHalfWidth - 0.28]],
    D: [[0.45, L / 2 - edge], [aisleHalfWidth + 0.28, W / 2 - edge]],
  }
  const errors: string[] = []
  const beds: BedLayout[] = []
  const zones: ZoneLayout[] = []

  for (const zone of config.zones) {
    const [xRange, zRange] = bounds[zone.id]
    const result = generateBeds({
      zoneId: zone.id,
      crop: zone.crop,
      bedCount: zone.bedCount,
      xRange,
      zRange,
      bedWidth: config.layout.bedWidth,
      bedGap: config.layout.bedGap,
    })
    if (!result.valid) {
      errors.push(result.reason)
      continue
    }
    beds.push(...result.beds)
    zones.push({
      id: zone.id,
      crop: zone.crop,
      bounds: [xRange[0], xRange[1], zRange[0], zRange[1]],
      beds: result.beds.map((bed) => bed.id),
      anchor: [(xRange[0] + xRange[1]) / 2, 1.7, (zRange[0] + zRange[1]) / 2],
    })
  }

  const colliders: Collider[] = [
    { id: 'WallN', min: [-16, 0, -9.2], max: [16, 3.6, -8.75] },
    { id: 'WallS', min: [-16, 0, 8.75], max: [16, 3.6, 9.2] },
    { id: 'WallW', min: [-16.2, 0, -9], max: [-15.75, 3.6, 9] },
    { id: 'WallE', min: [15.75, 0, -9], max: [16.2, 3.6, 9] },
    ...beds.map((bed) => ({
      id: bed.id,
      min: [bed.position[0] - bed.size[0] / 2, 0, bed.position[2] - bed.size[2] / 2] as [number, number, number],
      max: [bed.position[0] + bed.size[0] / 2, 0.7, bed.position[2] + bed.size[2] / 2] as [number, number, number],
    })),
  ]
  const devices = generateDevices(config, zones)
  const anchors: InteriorLayout['anchors'] = {
    Camera_Inside_Start: [-14.2, 1.7, 0],
    Camera_Inside_Center: [0, 1.7, 0],
    Entrance_Inside_Anchor: [-14.2, 1.7, 0],
    DeviceArea_Focus: [13.5, 1.7, 0],
  }
  for (const zone of zones) anchors[`Zone_${zone.id}_Focus`] = zone.anchor
  for (const device of devices) anchors[`${device.id}_Anchor`] = device.position

  return { valid: errors.length === 0, errors, beds, zones, devices, colliders, anchors }
}
