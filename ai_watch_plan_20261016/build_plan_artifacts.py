from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET
import markdown

OUT=Path(__file__).resolve().parent
title='棚智未来 · AI值守与协同运营'
mx=ET.Element('mxfile',host='drawio',version='26.0.0')
dg=ET.SubElement(mx,'diagram',name='值守运营方案',id='watch-plan')
model=ET.SubElement(dg,'mxGraphModel',dx='1440',dy='760',grid='1',gridSize='10',page='1',pageWidth='1440',pageHeight='760')
root=ET.SubElement(model,'root')
ET.SubElement(root,'mxCell',id='0')
ET.SubElement(root,'mxCell',id='1',parent='0')
seq=1
def node(label,x,y,w,h,fill='#ffffff',stroke='#dfe7d8',font=16,style='',parent='1'):
 global seq
 seq+=1
 ident=str(seq)
 c=ET.SubElement(root,'mxCell',id=ident,value=label,style='rounded=1;whiteSpace=wrap;html=1;fontFamily=Microsoft YaHei;fontColor=#284a36;fillColor='+fill+';strokeColor='+stroke+';fontSize='+str(font)+';spacing=12;arcSize=12;'+style,vertex='1',parent=parent)
 ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
 return ident
def edge(a,b,waypoints=None,label='',style=''):
 global seq
 seq+=1
 c=ET.SubElement(root,'mxCell',id=str(seq),value=label,style='edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeColor=#6e9261;strokeWidth=2;fontFamily=Microsoft YaHei;fontSize=12;fontColor=#6e8265;labelBackgroundColor=#ffffff;'+style,edge='1',parent='1',source=a,target=b)
 g=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
 if waypoints:
  pts=ET.SubElement(g,'Array',attrib={'as':'points'})
  for x,y in waypoints:ET.SubElement(pts,'mxPoint',x=str(x),y=str(y))
 return c
node('<b>'+title+'</b>',50,30,1300,52,font=28,style='fillColor=none;strokeColor=none;align=left;')
node('建设方案｜复用现有监测、任务、审批与复查；新增后台主动触发与统一值守中心',50,87,1300,36,font=14,style='fillColor=none;strokeColor=none;align=left;fontColor=#819175;')
labels=[
'<b>01 数据进入</b><br>环境采样 · 设备状态<br>任务反馈 · 定时计划',
'<b>02 质量与权限</b><br>归属 · 时间 · 单位<br>有效性 · 采样连续性',
'<b>03 事件规则</b><br>持续异常 · 去重合并<br>恢复边界 · 有限升级',
'<b>04 AI协同分析</b><br>检索依据 · 形成步骤<br>动作校验 · 人工确认',
'<b>05 执行与记录</b><br>首期：任务与站内通知<br>二期：受控设备接口',
'<b>06 复查与汇总</b><br>有效新数据 · 现场反馈<br>恢复 / 转人工 · 日报']
ids=[]
for i,label in enumerate(labels):ids.append(node(label,50+i*220,155,190,110,fill='#edf3e7' if i in (3,5) else '#ffffff',font=15))
for a,b in zip(ids,ids[1:]):edge(a,b,style='exitX=1;exitY=0.5;entryX=0;entryY=0.5;')
edge(ids[5],ids[2],waypoints=[(1245,305),(585,305)],label='未达标 / 证据不足：有限重评或转人工',style='exitX=0.5;exitY=1;entryX=0.5;entryY=1;dashed=1;')
container=node('首期四项能力',50,355,1290,165,fill='#f8faf4',font=16,style='swimlane;startSize=38;container=1;pointerEvents=0;horizontal=1;align=left;')
for i,(name,desc) in enumerate([
('环境异常跟踪','连续异常 → 任务 → 反馈 → 复查'),
('设备与数据检查','延迟 / 中断 / 可疑读数 → 核查'),
('农事提醒与复查','临期 / 逾期 → 提醒 → 有限升级'),
('每日生产汇总','后端统计 → AI解释 → 版本留存')]):
 node('<b>'+name+'</b><br>'+desc,20+i*315,57,300,85,fill='#ffffff',font=14,parent=container)
node('<b>贯穿全程：权限与委托 · 数据时效 · 幂等去重 · 审批 · 心跳与恢复 · 审计 · 人工接管</b><br><br>当前图为拟建设方案。设备操作需独立联调与现场验证；环境变化不自动证明某项操作有效。',50,555,1290,100,fill='#fbf3e4',stroke='#eadcc0',font=15)
ET.indent(mx)
ET.ElementTree(mx).write(OUT/'AI值守运营流程.drawio',encoding='utf-8',xml_declaration=True)

plan_path=OUT/'棚智未来_AI值守与协同运营_详细方案.md'
md=plan_path.read_text(encoding='utf-8')
lines=[]
for line in md.splitlines():
 if re.match(r'^(?:\d+\. |\- )',line) and lines and lines[-1].strip() and not re.match(r'^(?:\d+\. |\- )',lines[-1]):
  lines.append('')
 lines.append(line)
md='\n'.join(lines)+'\n'
plan_path.write_text(md,encoding='utf-8')
converted=markdown.Markdown(extensions=['tables','toc','fenced_code'],extension_configs={'toc':{'title':'方案目录','toc_depth':'2'}})
body=converted.convert(md).replace('<table>','<div class="table-scroll"><table>').replace('</table>','</table></div>')
scenes=[
dict(name='环境异常',steps=['持续异常','核查有效数据','形成处置建议','确认或授权任务','人员反馈与复查','恢复或转人工'],detail='首期示例：番茄棚高湿。阈值和持续时间由农技人员审核配置；先核查数据，关联已有任务，复查使用有效新数据。'),
dict(name='设备与数据',steps=['延迟或中断','区分链路原因','查询设备状态','有限重试与检修任务','连续有效数据恢复','记录缺口与结果'],detail='没有心跳能力时称为数据中断，不直接认定设备断线。原始可疑值保留；不自动修改校准参数或重启生产设备。'),
dict(name='农事跟进',steps=['临期或逾期','核查负责人','去重提醒','有限升级或确认调整','读取反馈与复查','依条件完成或转交'],detail='任务状态和环境目标分别核验。环境恢复不证明现场任务已执行；人员拒绝、暂停或撤权后不得继续派发对应动作。'),
dict(name='生产日报',steps=['按时区到期','统计前日完整区间','核对数据缺失','AI组织解释','发布站内报告','追溯证据与版本'],detail='默认07:30生成前一日完整日报，另附当前待办。统计由后端计算，模型不可用时保留统计版；缺失数据不能写成正常。')
]
css="""
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f5ef;color:#294333;font-family:'Microsoft YaHei','PingFang SC',sans-serif;font-size:15px;line-height:1.9}
header{background:#fffefb;border-bottom:1px solid #e0e7d8;padding:36px max(24px,calc((100vw - 1250px)/2)) 30px}header small{color:#809273;font-size:12px;letter-spacing:.15em}
header h1{font-size:31px;margin:8px 0 10px;line-height:1.45}header p{color:#7a8970;margin:0;max-width:900px}.badge{display:inline-block;padding:3px 10px;background:#eaf1e2;color:#557647;border-radius:6px;font-size:12px;margin-top:15px}
.layout{max-width:1300px;margin:26px auto 70px;padding:0 24px;display:grid;grid-template-columns:222px minmax(0,1fr);gap:24px}
nav{position:sticky;top:20px;align-self:start;background:#fbfcf7;border:1px solid #e1e7d9;border-radius:15px;padding:16px;font-size:12px;max-height:calc(100vh - 40px);overflow:auto}
nav .toctitle{font-weight:700;color:#35573b}nav ul{list-style:none;padding:0;margin:9px 0}nav li{margin:9px 0}nav .toc>ul>li>a{display:none}a{color:#24694e;text-decoration:none}a:hover{text-decoration:underline}
main{min-width:0}.intro,.document{background:#fff;border:1px solid #e1e7d9;border-radius:16px;padding:26px;margin-bottom:22px}.intro h2{margin:0 0 12px;font-size:19px}
.tabs{display:flex;gap:7px;flex-wrap:wrap}.tabs button{font:inherit;font-size:12px;border:1px solid #dce6d3;border-radius:7px;padding:7px 13px;background:#f5f8ef;color:#658156;cursor:pointer}
.tabs button[aria-selected=true]{color:white;background:#24694e;border-color:#24694e}.steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:18px 0}
.step{background:#f4f7ee;border:1px solid #e1e8d8;border-radius:9px;padding:12px;line-height:1.7;font-size:12px}.step b{display:block;color:#9aaa88;font-size:11px;margin-bottom:4px}
#scenario-detail{font-size:12px;color:#74866b;margin:0}.document>h1{display:none}.document>p:first-of-type{color:#89947e;font-size:12px}
.document h2{font-size:22px;line-height:1.6;margin:38px 0 16px;border-top:1px solid #e8eddf;padding-top:22px;scroll-margin-top:18px}.document h3{font-size:17px;margin:25px 0 12px;color:#3c613e;scroll-margin-top:20px}
.document p{margin:12px 0}.document li{margin:7px 0}.document strong{color:#244f33}.table-scroll{overflow:auto;margin:17px 0;border:1px solid #e2e8db;border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:12px;line-height:1.85;min-width:520px}th{background:#edf3e6;text-align:left;color:#49673c}th,td{padding:11px 12px;border-bottom:1px solid #e8eddf;vertical-align:top}tr:last-child td{border-bottom:0}
.doc-actions{margin-top:16px;display:flex;gap:16px;flex-wrap:wrap;font-size:12px}button:focus-visible,a:focus-visible{outline:2px solid #24694e;outline-offset:3px}
@media(max-width:850px){.layout{grid-template-columns:1fr;padding:0 15px}nav{position:static;max-height:none}nav ul{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}.intro,.document{padding:20px}header{padding:25px 20px}header h1{font-size:25px}}
@media(max-width:450px){nav ul{grid-template-columns:1fr}.steps{grid-template-columns:1fr 1fr}.document h2{font-size:19px}.document{font-size:14px}}
@media print{body{background:white}.layout{display:block;margin:0;padding:0}nav,.intro,.doc-actions{display:none}.document{border:0;padding:0}header{padding:0 0 20px}.table-scroll{overflow:visible}table{min-width:0}h2,h3{break-after:avoid}tr{break-inside:avoid}}
"""
html='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'｜详细建设方案</title><style>'+css+'</style></head><body><header><small>SMART GREENHOUSE · OPERATIONS PLAN</small><h1>'+title+'</h1><p>环境异常跟踪、设备与数据检查、农事提醒与复查、每日生产汇总。依据当前代码基础制定，明确新增范围、执行权限与验收条件。</p><span class="badge">建设方案 V1.0 · 2026年10月16日 · 尚未启用自动托管</span><div class="doc-actions"><a href="棚智未来_AI值守与协同运营_详细方案.md" download>下载完整说明</a><a href="AI值守运营流程.drawio" download>下载可编辑流程图</a><a href="#" id="print">打印 / 另存为PDF</a></div></header><div class="layout"><nav aria-label="方案目录">'+converted.toc+'</nav><main><section class="intro"><h2>四项能力怎样工作</h2><div class="tabs" role="tablist" aria-label="值守场景"></div><div id="scenario" role="tabpanel"><div class="steps"></div><p id="scenario-detail"></p></div></section><article class="document">'+body+'</article></main></div><script>const scenes='+json.dumps(scenes,ensure_ascii=False)+';const tabs=document.querySelector(".tabs");function show(i){document.querySelectorAll(".tabs button").forEach((b,k)=>{b.setAttribute("aria-selected",k===i?"true":"false");b.tabIndex=k===i?0:-1});document.querySelector(".steps").replaceChildren(...scenes[i].steps.map((t,k)=>{let d=document.createElement("div");d.className="step";let n=document.createElement("b");n.textContent="0"+(k+1);d.append(n,document.createTextNode(t));return d}));document.querySelector("#scenario-detail").textContent=scenes[i].detail;document.querySelector("#scenario").setAttribute("aria-labelledby","scene-"+i)}scenes.forEach((s,i)=>{const b=document.createElement("button");b.type="button";b.role="tab";b.id="scene-"+i;b.textContent=s.name;b.setAttribute("aria-controls","scenario");b.onclick=()=>show(i);b.onkeydown=e=>{if(["ArrowLeft","ArrowRight","Home","End"].includes(e.key)){e.preventDefault();let n=e.key==="Home"?0:e.key==="End"?scenes.length-1:(i+(e.key==="ArrowRight"?1:-1)+scenes.length)%scenes.length;show(n);tabs.children[n].focus()}};tabs.append(b)});show(0);document.querySelector("#print").onclick=e=>{e.preventDefault();window.print()};</script></body></html>'
(OUT/'方案阅读版.html').write_text(html,encoding='utf-8')
print('Created editable diagram and self-contained reading page.')

