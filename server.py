import os, json, sqlite3, hashlib, secrets, shutil, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from datetime import datetime, timezone
DB=os.getenv('VCMC_DB','vcmp.db'); HOST=os.getenv('HOST','0.0.0.0'); PORT=int(os.getenv('PORT','10000'))
ADMIN_EMAIL=os.getenv('VCMC_ADMIN_EMAIL','vcmcpusat@gmail.com'); ADMIN_PASSWORD=os.getenv('VCMC_ADMIN_PASSWORD','CHANGE-ME')
REAL_MONEY=os.getenv('VCMC_REAL_MONEY_ENABLED','false').lower()=='true'; BACKUP_DIR=os.getenv('VCMC_BACKUP_DIR','backups')
RULE_ID='VCMC-ALLOC-001'; RULE_VERSION='1.0.0'; FORMULA_VERSION='1.0.0'
def now(): return datetime.now(timezone.utc).isoformat()
def conn():
 c=sqlite3.connect(DB,check_same_thread=False); c.row_factory=sqlite3.Row; return c
def init():
 c=conn(); c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,password_hash TEXT,role TEXT); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER,expires REAL); CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,state TEXT,gross INTEGER,created_at TEXT); CREATE TABLE IF NOT EXISTS case_events(id INTEGER PRIMARY KEY,case_id TEXT,state TEXT,at TEXT,actor TEXT); CREATE TABLE IF NOT EXISTS payment_instructions(id INTEGER PRIMARY KEY,case_id TEXT,provider_id TEXT,status TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,case_id TEXT,amount INTEGER,kind TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS allocations(id INTEGER PRIMARY KEY,case_id TEXT,dest TEXT,amount INTEGER,kind TEXT); CREATE TABLE IF NOT EXISTS destinations(id TEXT PRIMARY KEY,label TEXT,kind TEXT,active INTEGER); CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY,case_id TEXT,kind TEXT,sha256 TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS reconciliations(id INTEGER PRIMARY KEY,case_id TEXT,status TEXT,expected INTEGER,executed INTEGER,received INTEGER,ledger INTEGER,created_at TEXT); CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at TEXT,actor TEXT,action TEXT,entity TEXT,details TEXT); CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY,response TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS backups(id INTEGER PRIMARY KEY,path TEXT,sha256 TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS providers(id TEXT PRIMARY KEY,name TEXT,execution_verified INTEGER);''')
 if not c.execute('SELECT 1 FROM users WHERE email=?',(ADMIN_EMAIL,)).fetchone(): c.execute('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)',(ADMIN_EMAIL,hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest(),'SOVEREIGN'))
 for row in [('DEST-001','MODAL_PENGEMBANGAN','CAPITAL'),('DEST-002','AMAL_ZAKAT_RESERVE','AMAL_ZAKAT_RESERVE'),('DEST-003','HAK_CIPTA_IP','IP')]: c.execute('INSERT OR IGNORE INTO destinations VALUES(?,?,?,1)',row)
 c.execute("INSERT OR IGNORE INTO providers VALUES('PJP-SIM-001','Simulation Provider',0)"); c.commit(); c.close()
def calc(g):
 g=int(g); z=g*25//1000; r=g-z; m=r*40//100; p=r*40//100; a=r-m-p; ip=p*40//100; dev=p*40//100; reserve=p-ip-dev
 return {'gross':g,'zakat':z,'mitra':m,'pusat':p,'amal':a,'ip':ip,'development':dev,'reserve':reserve,'formula_version':FORMULA_VERSION}
def audit(actor,action,entity,details=''):
 c=conn(); c.execute('INSERT INTO audit(at,actor,action,entity,details) VALUES(?,?,?,?,?)',(now(),actor,action,entity,details)); c.commit(); c.close()
class H(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def sendj(self,code,obj):
  b=json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
 def body(self): return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
 def auth(self):
  t=self.headers.get('Authorization','').replace('Bearer ',''); c=conn(); r=c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(t,time.time())).fetchone(); c.close(); return dict(r) if r else None
 def do_GET(self):
  p=urlparse(self.path).path
  if p=='/':
   html='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>VCMC-VP Secure Admin Login</title><style>body{font-family:system-ui,sans-serif;max-width:420px;margin:60px auto;padding:24px}input,button{width:100%;padding:12px;margin:8px 0;box-sizing:border-box}button{cursor:pointer}.msg{margin-top:12px}</style></head><body><h1>VCMC-VP</h1><h2>Secure Admin Login</h2><input id="email" type="email" placeholder="Admin email"><input id="password" type="password" placeholder="Admin password"><button onclick="login()">Login</button><div id="msg" class="msg"></div><script>async function login(){const msg=document.getElementById('msg');msg.textContent='Signing in...';try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:document.getElementById('email').value,password:document.getElementById('password').value})});const d=await r.json();if(!r.ok){msg.textContent='Login failed.';return}const m=await fetch('/api/metrics');const md=await m.json();msg.textContent='Login successful. Role: '+d.role+' | Cases: '+md.cases+' | Audit events: '+md.audit_events;}catch(e){msg.textContent='Connection error.'}}</script></body></html>'''
   b=html.encode(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b); return
  if p=='/health': return self.sendj(200,{'status':'ok','machine':'VCMC-VP','real_money_enabled':REAL_MONEY})
  if p=='/api/system/readiness':
   c=conn(); provider=bool(c.execute('SELECT 1 FROM providers WHERE execution_verified=1').fetchone()); c.close(); return self.sendj(200,{'ready':not REAL_MONEY,'real_money_enabled':REAL_MONEY,'real_pjp_execution_verified':provider})
  if p=='/api/rule': return self.sendj(200,{'rule_id':RULE_ID,'version':RULE_VERSION,'formula_version':FORMULA_VERSION})
  if p=='/api/metrics':
   c=conn(); n=c.execute('SELECT COUNT(*) FROM cases').fetchone()[0]; a=c.execute('SELECT COUNT(*) FROM audit').fetchone()[0]; c.close(); return self.sendj(200,{'cases':n,'audit_events':a})
  if p=='/api/api': return self.sendj(200,{'version':'v1','routes':['/api/login','/api/cases','/api/calculate','/api/allocate','/api/state','/api/evidence','/api/payment-instructions','/api/backups/create','/api/reconciliation','/api/metrics','/api/system/readiness']})
  if p=='/api/destinations':
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,label,kind,active FROM destinations')]; c.close(); return self.sendj(200,{'destinations':rows})
  return self.sendj(404,{'error':'not_found'})
 def do_POST(self):
  p=urlparse(self.path).path
  try: data=self.body()
  except: return self.sendj(400,{'error':'invalid_json'})
  if p=='/api/login':
   c=conn(); u=c.execute('SELECT * FROM users WHERE email=? AND password_hash=?',(data.get('email',''),hashlib.sha256(data.get('password','').encode()).hexdigest())).fetchone()
   if not u: c.close(); return self.sendj(401,{'error':'unauthorized'})
   tok=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions VALUES(?,?,?)',(tok,u['id'],time.time()+86400)); c.commit(); c.close(); audit(u['email'],'LOGIN','USER',u['email']); return self.sendj(200,{'token':tok,'role':u['role']})
  user=self.auth()
  if not user: return self.sendj(401,{'error':'unauthorized'})
  if p=='/api/calculate': return self.sendj(200,calc(data.get('gross',0)))
  if p=='/api/allocate':
   g=int(data.get('gross',0)); x=calc(g); cid=data.get('case_id')
   if not cid: return self.sendj(400,{'error':'case_id_required'})
   c=conn(); c.execute('DELETE FROM allocations WHERE case_id=?',(cid,));
   rows=[('DEST-002',x['zakat'],'ZAKAT'),('MITRA',x['mitra'],'MITRA'),('DEST-001',x['development'],'DEVELOPMENT'),('DEST-003',x['ip'],'IP'),('DEST-002',x['reserve'],'RESERVE'),('DEST-002',x['amal'],'AMAL')]
   for d,a,k in rows: c.execute('INSERT INTO allocations(case_id,dest,amount,kind) VALUES(?,?,?,?)',(cid,d,a,k)); c.execute('INSERT INTO ledger(case_id,amount,kind,created_at) VALUES(?,?,?,?)',(cid,a,k,now()))
   c.commit(); c.close(); audit(user['email'],'ALLOCATE',cid,RULE_ID+'@'+RULE_VERSION); return self.sendj(200,{'case_id':cid,'allocation':rows,'formula_version':FORMULA_VERSION})
  if p=='/api/state':
   cid=data.get('case_id'); state=data.get('state')
   allowed={'CREATED','PENDING','VALIDATING','VERIFIED','AUTHORIZED','PROCESSING','EXECUTED','EVIDENCE_PENDING','RECONCILIATION_PENDING','RECONCILED','COMPLETED','HOLD','BLOCKED','FAILED','CANCELLED','UNKNOWN','ARCHIVED'}
   if state not in allowed: return self.sendj(400,{'error':'invalid_state'})
   c=conn(); c.execute('UPDATE cases SET state=? WHERE id=?',(state,cid)); c.execute('INSERT INTO case_events(case_id,state,at,actor) VALUES(?,?,?,?)',(cid,state,now(),user['email'])); c.commit(); c.close(); audit(user['email'],'STATE',cid,state); return self.sendj(200,{'case_id':cid,'state':state})
  if p=='/api/evidence':
   cid=data.get('case_id'); payload=json.dumps(data.get('payload',{}),sort_keys=True).encode(); h=hashlib.sha256(payload).hexdigest(); c=conn(); c.execute('INSERT INTO evidence(case_id,kind,sha256,created_at) VALUES(?,?,?,?)',(cid,data.get('kind','CASE_EVIDENCE'),h,now())); c.commit(); c.close(); audit(user['email'],'EVIDENCE',cid,h); return self.sendj(201,{'case_id':cid,'sha256':h})
  if p=='/api/payment-instructions':
   if REAL_MONEY: return self.sendj(403,{'error':'real_money_execution_disabled_until_provider_verified'})
   cid=data.get('case_id'); provider=data.get('provider_id','PJP-SIM-001'); iid='PI-'+secrets.token_hex(8); c=conn(); c.execute('INSERT INTO payment_instructions(case_id,provider_id,status,created_at) VALUES(?,?,?,?)',(cid,provider,'HOLD_SIMULATION',now())); c.commit(); c.close(); audit(user['email'],'PAYMENT_INSTRUCTION',cid,iid); return self.sendj(200,{'instruction_id':iid,'case_id':cid,'provider_id':provider,'status':'HOLD_SIMULATION','executed':False})
  if p=='/api/cases':
   key=self.headers.get('Idempotency-Key') or data.get('request_id')
   if not key: return self.sendj(400,{'error':'idempotency_key_required'})
   c=conn(); old=c.execute('SELECT response FROM idempotency WHERE key=?',(key,)).fetchone()
   if old: c.close(); return self.sendj(200,json.loads(old['response']))
   cid='CASE-'+secrets.token_hex(8); result={'case_id':cid,'request_id':key,'state':'CREATED'}; c.execute('INSERT INTO cases VALUES(?,?,?,?,?)',(cid,key,'CREATED',int(data.get('gross',0)),now())); c.execute('INSERT INTO idempotency VALUES(?,?,?)',(key,json.dumps(result),now())); c.commit(); c.close(); audit(user['email'],'CREATE_CASE','CASE',cid); return self.sendj(201,result)
  if p=='/api/reconciliation':
   c=conn(); cid=data['case_id']; vals=[int(data.get(k,0)) for k in ('expected','executed','received','ledger')]; status='RECONCILED' if len(set(vals))==1 else 'EXCEPTION'; c.execute('INSERT INTO reconciliations(case_id,status,expected,executed,received,ledger,created_at) VALUES(?,?,?,?,?,?,?)',(cid,status,*vals,now())); c.commit(); c.close(); audit(user['email'],'RECONCILE',cid,status); return self.sendj(200,{'case_id':cid,'status':status,'expected':vals[0],'executed':vals[1],'received':vals[2],'ledger':vals[3]})
  if p=='/api/backups/create':
   os.makedirs(BACKUP_DIR,exist_ok=True); target=os.path.join(BACKUP_DIR,'vcmp-'+str(int(time.time()))+'.db'); shutil.copy2(DB,target); h=hashlib.sha256(open(target,'rb').read()).hexdigest(); c=conn(); c.execute('INSERT INTO backups(path,sha256,created_at) VALUES(?,?,?)',(target,h,now())); c.commit(); c.close(); audit(user['email'],'BACKUP','SYSTEM',h); return self.sendj(200,{'path':target,'sha256':h})
  return self.sendj(404,{'error':'not_found'})
if __name__=='__main__': init(); ThreadingHTTPServer((HOST,PORT),H).serve_forever()
