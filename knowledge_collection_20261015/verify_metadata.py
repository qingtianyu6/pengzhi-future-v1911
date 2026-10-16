import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
DOIS=['10.1515/intag-2017-0005','10.1016/j.scienta.2019.01.006','10.1111/j.1364-3703.2007.00417.x','10.1016/j.atech.2025.101020','10.11869/hnxb.2013.09.1401','10.1016/j.scienta.2026.115180']
def get(doi):
 try:
  with urllib.request.urlopen('https://api.crossref.org/works/'+doi,timeout=15) as r:
   m=json.load(r)['message']
  return dict(doi=doi,title=m.get('title'),authors=[(a.get('given','')+' '+a.get('family','')).strip() for a in m.get('author',[])],journal=m.get('container-title'),published=m.get('published'),volume=m.get('volume'),issue=m.get('issue'),page=m.get('page'),article=m.get('article-number'),sources=['crossref'],cross_validated=False)
 except Exception as e:return dict(doi=doi,error=str(e))
with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(get,DOIS))
Path(__file__).with_name('paper_metadata.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))

