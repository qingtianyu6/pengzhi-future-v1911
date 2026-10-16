from pathlib import Path
import re
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
plan=OUT/'棚智未来_AI农艺师_产品设计方案.md'
lines=[]
for line in plan.read_text(encoding='utf-8').splitlines():
 if re.match(r'^(?:\d+\. |\- )',line) and lines and lines[-1].strip() and not re.match(r'^(?:\d+\. |\- )',lines[-1]):
  lines.append('')
 lines.append(line)
plan.write_text('\n'.join(lines)+'\n',encoding='utf-8')

preview=OUT/'AI农艺师_交互概念预览.html'
html=preview.read_text(encoding='utf-8')
html=html.replace('<i>0','<i aria-hidden="true">0')
html=html.replace("p.textContent=document.getElementById('research-question').value.trim();const f=","p.textContent=studyQuestion;const f=")
html=html.replace("addedScenario?'方案 '+chosen+' · 未来'+range+'天'","addedScenario?'方案 '+scenarioSnapshot.chosen+' · 未来'+scenarioSnapshot.range+'天'")
html=html.replace("addedScenario?'按方案 '+chosen+' 组织观察","addedScenario?'按方案 '+scenarioSnapshot.chosen+' 组织观察")
html=html.replace("const d=explanations[b.dataset.action];showDialog(d[0],d.slice(1))","if(b.dataset.action==='plan-diff'){showDialog('当前计划关联',['方案：'+(addedScenario?'方案 '+scenarioSnapshot.chosen+' · 未来'+scenarioSnapshot.range+'天':'尚未加入'),'研究：'+(studyCreated?'已生成草案，尚未开展观察。':'尚未生成研究草案。'),'技能：'+(selectedSkill?skillNames[selectedSkill]:'尚未选择'),'当前只有预览草稿，没有写入正式任务。']);return}const d=explanations[b.dataset.action];showDialog(d[0],d.slice(1))")
preview.write_text(html,encoding='utf-8')

mx=ET.Element('mxfile',host='drawio',version='26.0.0')
dg=ET.SubElement(mx,'diagram',name='AI农艺师功能设计',id='agronomist-design')
model=ET.SubElement(dg,'mxGraphModel',dx='1400',dy='760',grid='1',gridSize='10',page='1',pageWidth='1400',pageHeight='760')
root=ET.SubElement(model,'root')
ET.SubElement(root,'mxCell',id='0')
ET.SubElement(root,'mxCell',id='1',parent='0')
seq=1
def node(label,x,y,w,h,fill='#ffffff',stroke='#dce5d1',font=16,extra=''):
 global seq
 seq+=1
 ident=str(seq)
 c=ET.SubElement(root,'mxCell',id=ident,value=label,vertex='1',parent='1',style='rounded=1;whiteSpace=wrap;html=1;fontFamily=Microsoft YaHei;fontColor=#2c5038;spacing=14;arcSize=12;fillColor='+fill+';strokeColor='+stroke+';fontSize='+str(font)+';'+extra)
 ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
 return ident
def edge(a,b,label='',points=None,extra=''):
 global seq
 seq+=1
 c=ET.SubElement(root,'mxCell',id=str(seq),value=label,source=a,target=b,edge='1',parent='1',style='edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeColor=#7f9d6b;strokeWidth=2;fontFamily=Microsoft YaHei;fontSize=12;fontColor=#7b8e69;labelBackgroundColor=#ffffff;'+extra)
 g=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
 if points:
  arr=ET.SubElement(g,'Array',attrib={'as':'points'})
  for x,y in points:ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))
node('<b>棚智未来 · 会学习的AI农艺师</b>',50,25,1300,58,font=29,extra='strokeColor=none;fillColor=none;align=left;')
node('产品设计方案｜以同一大棚、同一批次、同一生产问题连接五项能力',50,86,1300,40,font=15,extra='strokeColor=none;fillColor=none;align=left;fontColor=#89997b;')
names=[
'<b>01 生长档案</b><br>状态与来源<br>环境 · 观察 · 管理履历',
'<b>02 方案推演</b><br>共同基线 · 多种安排<br>输入 · 假设 · 情景结果',
'<b>03 生产研究</b><br>问题 · 假设 · 比较设计<br>观察 · 结果 · 反例',
'<b>04 农事技能</b><br>条件 · 步骤 · 验证<br>来源 · 版本 · 使用反馈',
'<b>05 目标编排</b><br>对象 · 人员 · 依赖<br>任务 · 观察 · 后续计划'
]
ids=[]
for i,name in enumerate(names):ids.append(node(name,50+i*260,170,220,125,fill='#edf3e5' if i in (0,3) else '#ffffff',font=16))
for a,b in zip(ids,ids[1:]):edge(a,b,extra='exitX=1;exitY=0.5;entryX=0;entryY=0.5;')
edge(ids[-1],ids[0],label='任务执行与观察反馈 → 回到同一案例，进入下一轮',points=[(1200,345),(160,345)],extra='exitX=0.5;exitY=1;entryX=0.5;entryY=1;dashed=1;')
node('<b>统一案例与证据</b><br>组织 / 大棚 / 区域 / 批次 · 环境记录 · 人工观察 · 知识引用 · 任务与复查 · 模型与技能版本',50,405,1260,92,fill='#f4f7ed',font=16)
node('<b>复用当前项目基础</b><br>监测预警 · 三维大棚 · 知识检索<br>农事任务 · Agent运行 · 审批与复查',50,535,600,110,font=15)
node('<b>按数据成熟度逐步开放</b><br>档案与流程 → 环境情景 → 生产研究 → 技能复用<br>状态估计与生长预测另行采集、校准和验证',690,535,620,110,fill='#fbf3e3',stroke='#e6d7b6',font=15)
node('建设方案示意。观察、推演、待验证解释与已完成结果分别记录；当前概念稿不连接实际预测、设备或任务写入。',50,674,1260,36,font=12,extra='strokeColor=none;fillColor=none;fontColor=#9aa68d;')
ET.indent(mx)
ET.ElementTree(mx).write(OUT/'AI农艺师_功能流程.drawio',encoding='utf-8',xml_declaration=True)
print('Design document, preview state and editable flow validated for generation.')

