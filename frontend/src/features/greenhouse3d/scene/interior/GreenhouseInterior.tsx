import type { GreenhouseInteriorConfig, InteriorLayout } from '../config/types'
import InteriorShell from './InteriorShell'
import BedSystem from './BedSystem'
import CropSystem from './CropSystem'
import PipeSystem from './PipeSystem'
import LightingSystem from './LightingSystem'
import DeviceSystem from './DeviceSystem'
import type { GrowthStage } from '../../../../types/cropBatch'

export default function GreenhouseInterior({
  config,
  layout,
  onBed,
  onDevice,
  lightsOn,
  growthStage,
  inspection = false,
}: {
  config: GreenhouseInteriorConfig
  layout: InteriorLayout
  onBed: (id: string) => void
  onDevice: (id: string) => void
  lightsOn: boolean
  growthStage: GrowthStage | null
  inspection?: boolean
}) {
  return (
    <group>
      <InteriorShell inspection={inspection} aisleWidth={config.layout.mainAisleWidth} />
      <BedSystem beds={layout.beds} onSelect={onBed} />
      <CropSystem beds={layout.beds} greenhouseId={config.greenhouseId} growthStage={growthStage} onSelect={onBed} />
      {!inspection && (
        <>
          <PipeSystem sprinklers={config.devices.sprinklers} />
          <LightingSystem count={config.devices.growLights} on={lightsOn} />
          <DeviceSystem devices={layout.devices} onSelect={onDevice} />
        </>
      )}
    </group>
  )
}
