import { useMemo } from 'react'
import type { BedLayout, CropType } from '../config/types'
import { generateCropInstances } from '../generation/cropGenerator'
import CropAssetLoader from '../assets/CropAssetLoader'
import SupportStringSystem from './SupportStringSystem'
import FoliageSystem from './FoliageSystem'
import type { GrowthStage } from '../../../../types/cropBatch'

export default function CropSystem({ beds, greenhouseId, growthStage, onSelect }: { beds: BedLayout[]; greenhouseId: string; growthStage: GrowthStage | null; onSelect: (bedId: string) => void }) {
  const all = useMemo(() => generateCropInstances(beds, greenhouseId, growthStage), [beds, greenhouseId, growthStage])
  const groups = useMemo(() => new Map(
    (['tomato', 'cucumber', 'pepper', 'strawberry', 'lettuce'] as CropType[]).flatMap((crop) =>
      [0, 1, 2].map((variant) => {
        const items = all.filter((item) => item.crop === crop && item.variant === variant)
        return [`${crop}-${variant}`, items] as const
      })
    )
  ), [all])
  return (
    <group>
      {(['tomato', 'cucumber', 'pepper', 'strawberry', 'lettuce'] as CropType[]).flatMap((crop) =>
        [0, 1, 2].map((variant) => {
          const items = groups.get(`${crop}-${variant}`) ?? []
          return items.length ? <CropAssetLoader key={`${crop}-${variant}`} crop={crop} variant={variant} instances={items} onSelect={onSelect} /> : null
        })
      )}
      <SupportStringSystem instances={all} growthStage={growthStage} />
      <FoliageSystem instances={all} onSelect={onSelect} />
    </group>
  )
}
