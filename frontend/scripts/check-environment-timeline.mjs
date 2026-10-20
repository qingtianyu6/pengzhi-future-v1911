import { readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import assert from 'node:assert/strict'
const require=createRequire(import.meta.url)
const ts=require('typescript')
const exports={}
const source=ts.transpileModule(readFileSync(new URL('../src/pages/Environment/timeline.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
new Function('exports',source)(exports)
const {buildTimeline}=exports
const now=Date.parse('2026-10-19T10:00:00Z'), hour=3600000
const row=(offset,value=24)=>({id:offset,greenhouse_id:1,recorded_at:new Date(now+offset*hour).toISOString(),temperature:value,air_humidity:70,soil_moisture:53,light_intensity:26.8,co2_concentration:737,quality_flag:'valid',source:'sensor'})
const history=[row(-2),row(-1),row(0)]
const prediction={status:'ready',input_end_time:history.at(-1).recorded_at,predictions:[1,2,3].map(h=>({forecast_time:new Date(now+h*hour).toISOString(),temperature_c:24+h,air_humidity_pct:70-h,par_umol_m2_s:400,lower_bounds:{air_temperature_c:22,air_humidity_pct:60},upper_bounds:{air_temperature_c:29,air_humidity_pct:80}}))}
const results=[]
function check(name,run){run();results.push(name);console.log(name)}
check('history and future use actual timestamps, not category spacing',()=>{const t=buildTimeline(history,prediction,'temperature',now,24,6);assert.equal(t.measured.length,3);assert.equal(t.forecast.length,4);assert.equal(t.forecast[1][0],now+hour);assert(t.intervalAvailable)})
check('missing forecast bounds do not fabricate a band',()=>{const p={...prediction,predictions:prediction.predictions.map(x=>({...x,lower_bounds:{},upper_bounds:{}}))};const t=buildTimeline(history,p,'temperature',now,24,6);assert(!t.intervalAvailable);assert.equal(t.lower.length,0)})
check('soil, light and CO2 do not borrow temperature or PAR forecasts',()=>{for(const key of ['soil_moisture','light_intensity','co2_concentration']){const t=buildTimeline(history,prediction,key,now,24,6);assert(!t.predictionAvailable);assert.equal(t.forecast.length,0)}})
check('sampling gaps remain broken lines',()=>{const t=buildTimeline([row(-8),row(-7),row(-6),row(0)],null,'temperature',now,24,6);assert(t.measured.some(([,v])=>v===null))})
check('stale measurements are not joined to a new forecast',()=>{const old=[row(-8),row(-7)];const p={...prediction,input_end_time:old.at(-1).recorded_at};const t=buildTimeline(old,p,'temperature',now,24,6);assert(t.stale);assert(t.forecast.every(([x])=>x>now))})
check('expired forecasts are not shown as future',()=>{const t=buildTimeline(history,{...prediction,predictions:prediction.predictions.map(p=>({...p,forecast_time:new Date(now-hour).toISOString()}))},'temperature',now,24,6);assert(!t.predictionAvailable)})
check('invalid ranges and missing values remain absent',()=>{const p={...prediction,predictions:prediction.predictions.map(x=>({...x,lower_bounds:{air_temperature_c:30},upper_bounds:{air_temperature_c:20}}))};const t=buildTimeline([row(-1,null),row(0)],p,'temperature',now,24,6);assert.equal(t.measured[0][1],null);assert(!t.intervalAvailable)})
check('same timestamp is deduplicated and future raw measurements excluded',()=>{const t=buildTimeline([row(0,22),row(0,23),row(1,99)],null,'temperature',now,24,6);assert.deepEqual(t.measured,[[now,23]])})
check('selected horizon limits the actual forecast points',()=>{const t=buildTimeline(history,prediction,'air_humidity',now,24,1);assert.equal(t.forecast.filter(([x])=>x>now).length,1);assert.equal(t.forecast.at(-1)[1],69)})
writeFileSync(new URL('../../.run/environment-redesign/timeline-results.json',import.meta.url),JSON.stringify({passed:results.length,checks:results},null,2))
