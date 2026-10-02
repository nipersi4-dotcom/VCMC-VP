import os,sys,tempfile,threading,json,urllib.request,urllib.error,hashlib,shutil
ROOT=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,ROOT)
with tempfile.TemporaryDirectory() as td:
 os.environ['VCMC_DB']=os.path.join(td,'v.db'); os.environ['VCMC_BACKUP_DIR']=os.path.join(td,'backups'); os.environ['VCMC_ADMIN_EMAIL']='vcmcpusat@gmail.com'; os.environ['VCMC_ADMIN_PASSWORD']='TEST-PASSWORD'; os.environ['VCMC_REAL_MONEY_ENABLED']='false'
 import importlib,server; importlib.reload(server); server.init(); srv=server.ThreadingHTTPServer(('127.0.0.1',0),server.H); threading.Thread(target=srv.serve_forever,daemon=True).start(); base=f'http://127.0.0.1:{srv.server_port}'
 def req(path,obj=None,token=None,headers=None):
  h={'Content-Type':'application/json'}; h.update(headers or {});
  if token:h['Authorization']='Bearer '+token
  try:
   r=urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(obj).encode() if obj is not None else None,headers=h,method='POST' if obj is not None else 'GET')); return r.status,json.loads(r.read())
  except urllib.error.HTTPError as e:
   return e.code,json.loads(e.read())
 assert req('/health')[1]['status']=='ok'
 # Failure behavior: reject unauthenticated access and invalid credentials without issuing a session.
 st,_=req('/api/evidence'); assert st==401
 st,_=req('/api/login',{'email':'vcmcpusat@gmail.com','password':'INVALID-TEST-CREDENTIAL'}); assert st==401
 st,login=req('/api/login',{'email':'vcmcpusat@gmail.com','password':'TEST-PASSWORD'}); assert st==200; tok=login['token']
 st,me=req('/api/me',token=tok); assert st==200 and me['authenticated'] is True
 st,home=req('/api/home',token=tok); assert st==200 and 'metrics' in home
 _,calc=req('/api/calculate',{'gross':100_000_000},tok); assert calc['zakat']==2_500_000 and calc['mitra']==39_000_000 and calc['pusat']==39_000_000 and calc['amal']==19_500_000
 _,c1=req('/api/cases',{'gross':100_000_000},tok,{'Idempotency-Key':'RM-001'}); _,c2=req('/api/cases',{'gross':999},tok,{'Idempotency-Key':'RM-001'}); assert c1==c2
 cid=c1['case_id']; _,a=req('/api/allocate',{'case_id':cid,'gross':100_000_000},tok); assert sum(x[1] for x in a['allocation'])==100_000_000
 _,s=req('/api/state',{'case_id':cid,'state':'UNKNOWN'},tok); assert s['state']=='UNKNOWN'; _,s=req('/api/state',{'case_id':cid,'state':'HOLD'},tok); assert s['state']=='HOLD'
 st,invalid=req('/api/state',{'case_id':cid,'state':'NOT_A_VALID_STATE'},tok); assert st==400 and invalid['error']=='invalid_state'
 _,e=req('/api/evidence',{'case_id':cid,'kind':'GOLDEN','payload':{'gross':100_000_000}},tok); assert len(e['sha256'])==64
 _,pi=req('/api/payment-instructions',{'case_id':cid},tok); assert pi['executed'] is False and pi['status']=='HOLD_SIMULATION'
 _,rec=req('/api/reconciliation',{'case_id':cid,'expected':100,'executed':100,'received':100,'ledger':100},tok); assert rec['status']=='RECONCILED'
 _,mismatch=req('/api/reconciliation',{'case_id':cid,'expected':100,'executed':90,'received':100,'ledger':100},tok); assert mismatch['status']=='EXCEPTION'
 _,b=req('/api/backups/create',{},tok); assert os.path.exists(b['path']) and hashlib.sha256(open(b['path'],'rb').read()).hexdigest()==b['sha256']
 _,ready=req('/api/system/readiness'); assert ready['real_money_enabled'] is False and ready['real_pjp_execution_verified'] is False
 _,lo=req('/api/logout',{},tok); assert lo['logged_out'] is True
 st,_=req('/api/me',token=tok); assert st==401
 srv.shutdown()
 print('VCMC-VP ROADMAP #3-#10 BUILD TEST: PASS')