import type { CropType } from './types'

export type CropProfile = {
  rowOffsets: number[]
  plantSpacing: number
  supportType: 'twine' | 'low' | 'none'
  dripLines: number
  heightVariation: [number, number]
  geometryVariants: number
  fruitDensity: number
}

export const cropProfiles: Record<CropType, CropProfile> = {
  tomato: { rowOffsets: [-0.22,0.22], plantSpacing: 0.66, supportType: 'twine', dripLines: 2, heightVariation: [0.94,1.06], geometryVariants: 3, fruitDensity: 0.68 },
  cucumber:{ rowOffsets: [-0.22,0.22], plantSpacing: 0.63, supportType: 'twine', dripLines: 2, heightVariation: [0.94,1.06], geometryVariants: 3, fruitDensity: 0.52 },
  pepper:{ rowOffsets: [-0.22,0.22], plantSpacing: 0.46, supportType: 'low', dripLines: 2, heightVariation: [0.95,1.05], geometryVariants: 3, fruitDensity: 0.46 },
  strawberry:{ rowOffsets: [-0.22,0.22], plantSpacing: 0.34, supportType: 'none', dripLines: 2, heightVariation: [0.95,1.05], geometryVariants: 3, fruitDensity: 0.40 },
  lettuce:{ rowOffsets: [-0.30,-0.10,0.10,0.30], plantSpacing: 0.29, supportType: 'none', dripLines: 2, heightVariation: [0.96,1.04], geometryVariants: 3, fruitDensity: 0 },
}
