import type { DeviceLayout } from '../config/types'
import DeviceAssetLoader from '../assets/DeviceAssetLoader'
export default function DeviceSystem({devices,onSelect}:{devices:DeviceLayout[];onSelect:(id:string)=>void}){return <group>{devices.filter(d=>d.type==='sensor'||d.type==='pump').map(d=><DeviceAssetLoader key={d.id} id={d.id} type={d.type} position={d.position} onClick={()=>onSelect(d.id)}/>)}</group>}
