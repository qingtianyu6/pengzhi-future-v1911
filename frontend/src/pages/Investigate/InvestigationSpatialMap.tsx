import { Button } from 'antd'

/** Location selector only: the drawing does not imply measured conditions. */
export function InvestigationSpatialMap({zone,counts,onSelect}:{zone:string;counts:Record<string,number>;onSelect:(zone:string)=>void}) {
  return <div className="iw-spatial-selector" aria-label="大棚区域选择器">
    <svg preserveAspectRatio="none" viewBox="0 0 400 155" role="img" aria-label={`异常位置标记：${zone}，区域示意`}>
      <defs><clipPath id="investigation-greenhouse-outline"><path d="M8 140V102Q10 12 200 12Q390 12 392 102V140Z"/></clipPath><g id="investigation-plant"><path d="M0 0V-27M0-6L-9-14M0-14L9-22" fill="none" stroke="#9bad91" strokeWidth="1.3"/><path d="M-9-14q-9-12 1-8q9 1 8 10M9-22q9-11 0-8q-8 2-9 10" fill="#dae4ce" stroke="#a6b698" strokeWidth=".7"/></g></defs>
      <g clipPath="url(#investigation-greenhouse-outline)">
        <path d="M8 140V102Q10 12 200 12Q390 12 392 102V140Z" fill="#f1f3eb"/>
        {['西侧','中央','东侧'].map((z,i)=><rect key={z} x={8+i*128} y="12" width="128" height="130" fill={zone===z?'#c8dbb5':'transparent'} opacity=".75"/>)}
        {[0,1,2].map(row=>Array.from({length:12},(_,i)=><use key={row+'-'+i} href="#investigation-plant" x={24+i*31} y={112+row*12} opacity={.5+row*.2}/>))}
        <path d="M8 91H392M8 115H392M45 35V140M90 20V140M140 13V140M200 12V140M260 13V140M310 20V140M355 35V140" fill="none" stroke="#bdc8bb" strokeWidth="1"/>
      </g>
      <path d="M8 140V102Q10 12 200 12Q390 12 392 102V140M13 140V104Q16 18 200 18Q384 18 387 104V140M8 140H392M72 140V101Q73 23 200 12M328 140V101Q327 23 200 12M136 140V99Q137 28 200 12M264 140V99Q263 28 200 12M200 12V140" fill="none" stroke="#aebaae" strokeWidth="1.2"/>
    </svg>
    <div className="iw-map-zones">{['西侧','中央','东侧'].map(z=><button key={z} type="button" aria-pressed={zone===z} onClick={()=>onSelect(z)}>{z}{counts[z]?' · '+counts[z]:''}</button>)}</div>
    <div className="iw-map-secondary"><small>区域示意 · 人工标记</small>{['北侧','南侧'].map(z=><Button key={z} size="small" type={zone===z?'primary':'text'} onClick={()=>onSelect(z)}>{z}{counts[z]?' · '+counts[z]:''}</Button>)}</div>
  </div>
}
