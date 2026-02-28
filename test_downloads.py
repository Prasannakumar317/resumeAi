import requests, re
base='http://127.0.0.1:5000'
s=requests.Session()
resp=s.get(base+'/builder')
html=resp.text
m=re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
csrf = m.group(1) if m else ''
print('csrf:', bool(csrf))

def test(tpl):
    data={'name':'AutoTest','email':'auto@test.com','phone':'555','summary':'x','declaration':'ok','template':tpl}
    if csrf: data['csrf_token']=csrf
    r=s.post(base+'/builder', data=data)
    print('tpl',tpl,'status',r.status_code,'ctype',r.headers.get('Content-Type'), 'disp', r.headers.get('Content-Disposition'))
    if r.status_code==200 and r.headers.get('Content-Type','').startswith('application/pdf'):
        # save file
        fname=f'uploads/AutoTest_{tpl}_test.pdf'
        with open(fname,'wb') as fh:
            fh.write(r.content)
        print('saved',fname,'size',len(r.content))

for t in ['modern','executive','creative','academic','minimal']:
    test(t)
