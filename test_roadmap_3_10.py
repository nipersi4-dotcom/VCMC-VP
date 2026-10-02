import os,sys,tempfile,threading,json,urllib.request,urllib.error,hashlib,shutil,sqlite3
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
 # Security/access gate: protected routes reject missing/invalid sessions and responses carry baseline security headers.
 rr=urllib.request.urlopen(urllib.request.Request(base+'/health'))
 assert rr.headers.get('X-Content-Type-Options')=='nosniff'
 assert rr.headers.get('X-Frame-Options')=='DENY'
 assert rr.headers.get('Cache-Control')=='no-store'
 st,_=req('/api/home'); assert st==401
 st,_=req('/api/activity'); assert st==401
 st,_=req('/api/evidence',token='invalid-token'); assert st==401
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
 # Backup -> restore -> verify: prove the durable case/evidence survives database replacement.
 with sqlite3.connect(b['path']) as bc:
  assert bc.execute('SELECT 1 FROM cases WHERE id=?',(cid,)).fetchone()
  assert bc.execute('SELECT 1 FROM evidence WHERE case_id=?',(cid,)).fetchone()
 srv.shutdown(); srv.server_close()
 shutil.copy2(b['path'],os.environ['VCMC_DB'])
 server.init(); srv=server.ThreadingHTTPServer(('127.0.0.1',0),server.H); threading.Thread(target=srv.serve_forever,daemon=True).start(); base=f'http://127.0.0.1:{srv.server_port}'
 st,login2=req('/api/login',{'email':'vcmcpusat@gmail.com','password':'TEST-PASSWORD'}); assert st==200; tok2=login2['token']
 st,home2=req('/api/home',token=tok2); assert st==200 and home2['metrics']['cases']>=1 and home2['metrics']['evidence']>=1 and home2['metrics']['reconciliations']>=2
 st,e2=req('/api/evidence',token=tok2); assert st==200 and e2['count']>=1 and e2['unverified']==e2['count']
 # Evidence + reconciliation final gate: verify recorded evidence/audit and both reconciliation outcomes.
 with sqlite3.connect(os.environ['VCMC_DB']) as vc:
  row=vc.execute('SELECT sha256 FROM evidence WHERE case_id=? ORDER BY id DESC LIMIT 1',(cid,)).fetchone(); assert row and len(row[0])==64
  rs=[x[0] for x in vc.execute('SELECT status FROM reconciliations WHERE case_id=? ORDER BY id',(cid,)).fetchall()]; assert 'RECONCILED' in rs and 'EXCEPTION' in rs
 st,activity=req('/api/activity',token=tok2); assert st==200 and len(activity['items'])>=1
 st,me2=req('/api/me',token=tok2); assert st==200 and me2['session_active'] is True
 # Even if the runtime flag is forced on, payment instruction must refuse execution.
 previous_real_money=server.REAL_MONEY; server.REAL_MONEY=True
 st,blocked=req('/api/payment-instructions',{'case_id':cid,'provider_id':'PJP-SIM-001'},tok2)
 server.REAL_MONEY=previous_real_money
 assert st==403 and blocked['error']=='real_money_execution_disabled_until_provider_verified'
 _,ready=req('/api/system/readiness'); assert ready['real_money_enabled'] is False and ready['real_pjp_execution_verified'] is False
 _,lo=req('/api/logout',{},tok); assert lo['logged_out'] is True
 st,_=req('/api/me',token=tok); assert st==401
 srv.shutdown()
 print('VCMC-VP ROADMAP #3-#10 BUILD TEST: PASS')