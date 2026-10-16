import * as THREE from 'three'
import type { BedLayout } from '../config/types'
import { cropProfiles } from '../config/cropProfiles'
import type { GrowthStage } from '../../../../types/cropBatch'

export type CropInstance = {
  id: string
  bedId: string
  crop: BedLayout['crop']
  variant: number
  matrix: THREE.Matrix4
  colorIndex: number
  fruitVisible: boolean
}

function hashString(input: string) {
  let h = 2166136261
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function unit(seed: number) {
  const x = Math.sin(seed * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

function fruitStageFactor(stage: GrowthStage | null) {
  if (stage === '苗期' || stage === '营养生长期' || stage === '伸蔓期') return 0
  if (stage === '开花坐果期') return 0.3
  if (stage === '果实膨大期') return 0.65
  return 1
}

function growthScales(stage: GrowthStage | null): [number, number] {
  if (stage === '苗期') return [0.48, 0.28]
  if (stage === '营养生长期') return [0.72, 0.55]
  if (stage === '伸蔓期') return [0.82, 0.70]
  if (stage === '开花坐果期') return [0.90, 0.84]
  if (stage === '果实膨大期') return [0.97, 0.94]
  return [1, 1]
}

export function generateCropInstances(beds: BedLayout[], greenhouseId: string, growthStage: GrowthStage | null) {
  const out: CropInstance[] = []
  const fruitFactor = fruitStageFactor(growthStage)
  const [canopyScale, heightScale] = growthScales(growthStage)
  for (const bed of beds) {
    const profile = cropProfiles[bed.crop]
    let plantIndex = 0
    for (let x = bed.xRange[0] + 0.42; x < bed.xRange[1] - 0.36; x += profile.plantSpacing) {
      for (let rowIndex = 0; rowIndex < profile.rowOffsets.length; rowIndex++) {
        const dz = profile.rowOffsets[rowIndex]
        const key = `${greenhouseId}|${bed.id}|${plantIndex}|${rowIndex}`
        const seed = hashString(key)
        const r1 = unit(seed + 11)
        const r2 = unit(seed + 101)
        const r3 = unit(seed + 503)
        const r4 = unit(seed + 907)
        const height = profile.heightVariation[0] + r3 * (profile.heightVariation[1] - profile.heightVariation[0])
        const scale = 0.84 + r2 * 0.32
        const rootY = growthStage === '苗期' ? 0.35 : growthStage === '营养生长期' ? 0.29 : 0.25
        const p = new THREE.Vector3(x + (r4 - 0.5) * 0.10, rootY, bed.position[2] + dz + (r2 - 0.5) * 0.08)
        const q = new THREE.Quaternion().setFromEuler(
          new THREE.Euler(0, r1 * Math.PI * 2, 0)
        )
        const s = new THREE.Vector3(scale * canopyScale, height * heightScale, scale * canopyScale)
        out.push({
          id: `Plant_${bed.id}_${plantIndex}_${rowIndex}`,
          bedId: bed.id,
          crop: bed.crop,
          variant: seed % profile.geometryVariants,
          matrix: new THREE.Matrix4().compose(p, q, s),
          colorIndex: seed % 3,
          fruitVisible: unit(seed + 1709) < profile.fruitDensity * fruitFactor,
        })
      }
      plantIndex++
    }
  }
  return out
}
