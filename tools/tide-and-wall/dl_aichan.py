import json,urllib.parse,urllib.request,os,concurrent.futures as cf
B='https://ai-chan-pose-gallery.ferngherng-lab.workers.dev/'
R='C:/Users/user/hermes-files/ai-war-mmv/00_ref/aichan/'
skip=('07_','12_','13_','14_')
items=json.load(open(R+'pz.json',encoding='utf-8'))+json.load(open(R+'cz.json',encoding='utf-8'))
items=[x for x in items if not x['角色'].startswith(skip)]
def get(x):
    out=R+x['原图'][len('img/aichan/'):]
    if os.path.exists(out) and os.path.getsize(out)>0: return 1
    os.makedirs(os.path.dirname(out),exist_ok=True)
    u=B+urllib.parse.quote(x['原图'])
    for _ in range(3):
        try:
            d=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=60).read()
            open(out,'wb').write(d);return 1
        except Exception as e: err=e
    print('FAIL',x['id'],err);return 0
with cf.ThreadPoolExecutor(8) as ex: ok=sum(ex.map(get,items))
print('ok',ok,'/',len(items))
