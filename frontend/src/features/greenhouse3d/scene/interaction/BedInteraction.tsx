export function bedMock(id:string,crop:string){return{title:id.replace('Bed_','').replaceAll('_',' ')+'号种植垄',作物:crop,温度:'24.6°C',空气湿度:'67%',土壤湿度:'61%',EC:'2.1',pH:'6.3',病害风险:'低',预计采收:'12天'}}
