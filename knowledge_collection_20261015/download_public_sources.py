import concurrent.futures, hashlib, json, re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests, fitz
from bs4 import BeautifulSoup

BASE=Path(__file__).resolve().parent
OUT=BASE/'已下载公开资料'
OUT.mkdir(exist_ok=True)
TASKS=[
dict(id='B6',filename='B6_FAO_温室蔬菜良好农业规范_2013.pdf',url='https://www.fao.org/4/i3284e/i3284e.pdf',expected=['greenhouse','vegetable'],kind='pdf'),
dict(id='B5',filename='B5_温室园艺_第2版_2024.pdf',url='https://edepot.wur.nl/704878',expected=['greenhouse','stanghellini'],kind='pdf'),
dict(id='B7',filename='B7_FAO56_作物蒸散与需水量_1998.pdf',url='https://appgeodb.nancy.inrae.fr/biljou/pdf/Allen_FAO1998.pdf',expected=['evapotranspiration','allen'],kind='pdf'),
dict(id='P1',filename='P1_番茄温湿度与VPD综述_2018.pdf',url='https://www.international-agrophysics.org/pdf-104321-35388?action=magazine&articleId=104321&controller=index&filename=Review-of-optimum-tempera.pdf&magSubpage=pdf&pdfId=35388',expected=['tomato','shamshiri'],kind='pdf'),
dict(id='G2',filename='G2_2025年设施蔬菜重要害虫生物防治技术方案.pdf',url='https://www.natesc.org.cn/admin/UeditorUploadFiles/file/20250319/6387800075611914063129687.pdf',expected=['设施蔬菜','生物防治'],kind='pdf'),
dict(id='G1',filename='G1_设施蔬菜冬季生产技术指导意见_2022.html',url='https://zzys.moa.gov.cn/tzgg/202210/t20221028_6414218.htm',expected=['设施蔬菜','冬季'],kind='html'),
]
HEADERS={'User-Agent':'PengzhiResearchCollection/1.0 (public academic resources; personal research)'}
def download(task):
 result=dict(task,downloaded_at=datetime.now(timezone.utc).isoformat())
 path=OUT/task['filename']
 try:
  r=requests.get(task['url'],headers=HEADERS,timeout=(15,55))
  result.update(http_status=r.status_code,resolved_url=r.url)
  r.raise_for_status()
  data=r.content
  if task['kind']=='pdf':
   if not data.lstrip().startswith(b'%PDF-'):raise ValueError('响应不是PDF；未把验证页或登录页当作全文')
   doc=fitz.open(stream=data,filetype='pdf')
   if doc.is_encrypted and not doc.authenticate(''):raise ValueError('PDF需要密码，未解密')
   text='\n'.join(doc[i].get_text() for i in range(min(len(doc),8)))
   combined=text+'\n'+'\n'.join(doc[i].get_text() for i in range(max(8,len(doc)-3),len(doc)))
   result.update(pages=len(doc),first_pages_excerpt=text[:1800])
   if not all(term.lower() in combined.lower() for term in task['expected']):raise ValueError('标题关键词无法全部匹配，需人工核查，未列为已下载全文')
   result['license_excerpt']='; '.join(line.strip() for line in combined.splitlines() if re.search(r'license|licence|copyright|creative commons|rights reserved|BY-NC',line,re.I))[:1500]
   doc.close()
  else:
   if r.encoding and r.encoding.lower()=='iso-8859-1':r.encoding=r.apparent_encoding
   text=BeautifulSoup(r.text,'html.parser').get_text('\n',strip=True)
   if not all(term in text for term in task['expected']) or len(text)<500:raise ValueError('网页正文未通过主题核查')
   data=r.content
   path.with_suffix('.txt').write_text(text,encoding='utf-8')
   result['characters']=len(text)
  path.write_bytes(data)
  result.update(status='downloaded_validated',local_file=str(path.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),rights_status='仅保存原文；知识库上线使用条件待单独审核')
  print('OK',task['id'],result.get('pages',result.get('characters')),len(data),flush=True)
 except Exception as e:
  result.update(status='not_downloaded',error=str(e))
  print('PENDING',task['id'],str(e)[:150],flush=True)
 return result
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 results=list(pool.map(download,TASKS))
(BASE/'download_manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
# Discover only publisher-provided links; do not bypass authentication or anti-bot challenges.
for ident,url in [('P5','https://www.hnxb.org.cn/CN/10.11869/hnxb.2013.09.1401'),('P3','https://bsppjournals.onlinelibrary.wiley.com/doi/full/10.1111/j.1364-3703.2007.00417.x'),('P4','https://www.sciencedirect.com/science/article/pii/S2772375525002539'),('P6','https://www.sciencedirect.com/science/article/pii/S0304423826005704')]:
 try:
  r=requests.get(url,headers=HEADERS,timeout=(10,20))
  if r.status_code!=200:print('DISCOVERY',ident,'HTTP',r.status_code,flush=True);continue
  soup=BeautifulSoup(r.content,'html.parser')
  links=[dict(text=a.get_text(' ',strip=True)[:70],url=urljoin(r.url,a.get('href','')),onclick=a.get('onclick')) for a in soup.find_all('a') if re.search(r'pdf|download|下载',a.get('href','')+' '+a.get_text(' ',strip=True)+' '+a.get('onclick',''),re.I)]
  meta=[str(m) for m in soup.select('meta[name=citation_pdf_url]')]
  (BASE/(ident+'_official_links.json')).write_text(json.dumps(dict(url=r.url,links=links,meta=meta),ensure_ascii=False,indent=2),encoding='utf-8')
  print('DISCOVERY',ident,json.dumps(dict(links=links[:12],meta=meta),ensure_ascii=False),flush=True)
 except Exception as e:print('DISCOVERY',ident,str(e),flush=True)

