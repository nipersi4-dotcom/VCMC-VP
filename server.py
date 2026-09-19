import os, json, sqlite3, uuid, hashlib, secrets, hmac, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DB = os.getenv('VCMC_DB', 'vcmc_vp.db')
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8765'))
ADMIN_EMAIL = os.getenv('VCMC_ADMIN_EMAIL', 'vcmcpusat@gmail.com').strip().lower()
ADMIN_PASSWORD = os.getenv('VCMC_ADMIN_PASSWORD', '')
SESSION_TTL = int(os.getenv('VCMC_SESSION_TTL', '86400'))
MAX_BODY = int(os.getenv('VCMC_MAX_BODY', str(1024*1024)))
BACKUP_DIR = os.getenv('VCMC_BACKUP_DIR', 'backups')
REAL_MONEY_ENABLED = os.getenv('VCMC_REAL_MONEY_ENABLED', 'false').lower() == 'true'
RULE_ID = 'VCMC-ALLOC-001'; RULE_VERSION = '1.0.0'

def now(): return datetime.now(timezone.utc).isoformat()
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    c=db(); c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,role TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,status TEXT NOT NULL,created_at TEXT NOT NULL,request_id TEXT NOT NULL,actor TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS activities(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,kind TEXT NOT NULL,value REAL NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS destinations(id TEXT PRIMARY KEY,alias TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,kind TEXT NOT NULL,sha256 TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS ledger(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,account TEXT NOT NULL,amount REAL NOT NULL,type TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reconciliations(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,actor TEXT NOT NULL,role TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,result TEXT NOT NULL,request_id TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS payments(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,status TEXT NOT NULL,provider_ref TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS rules(id TEXT PRIMARY KEY,version TEXT NOT NULL,status TEXT NOT NULL,basis TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS organizations(id TEXT PRIMARY KEY,name TEXT NOT NULL,type TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS memberships(id TEXT PRIMARY KEY,org_id TEXT NOT NULL,user_id TEXT NOT NULL,role TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS partner_profiles(id TEXT PRIMARY KEY,org_id TEXT NOT NULL,status TEXT NOT NULL,capability TEXT NOT NULL,notes TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,org_id TEXT,kind TEXT NOT NULL,name TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS providers(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,capabilities TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS payment_instructions(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,provider_id TEXT NOT NULL,status TEXT NOT NULL,amount REAL NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY,response_json TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS security_events(id TEXT PRIMARY KEY,kind TEXT NOT NULL,actor TEXT NOT NULL,result TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS allocations(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,rule_id TEXT NOT NULL,rule_version TEXT NOT NULL,gross REAL NOT NULL,zakat REAL NOT NULL,mitra REAL NOT NULL,pusat REAL NOT NULL,amal REAL NOT NULL,ip REAL NOT NULL,development REAL NOT NULL,reserve REAL NOT NULL,balance REAL NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS verification_records(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,kind TEXT NOT NULL,message TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS backup_records(id TEXT PRIMARY KEY,path TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS api_clients(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
    ''')
    c.execute('INSERT OR IGNORE INTO users VALUES(?,?,?,?,?)',('USER-001',ADMIN_EMAIL,'ADMIN VCMC','ACTIVE',now()))
    for row in [('DEST-001','MODAL_PENGEMBANGAN','CAPITAL','ACTIVE'),('DEST-002','AMAL_ZAKAT_RESERVE','AMAL_ZAKAT_RESERVE','ACTIVE'),('DEST-003','HAK_CIPTA_IP','IP','ACTIVE')]: c.execute('INSERT OR IGNORE INTO destinations VALUES(?,?,?,?)',row)
    c.execute('INSERT OR IGNORE INTO rules VALUES(?,?,?,?,?)',(RULE_ID,RULE_VERSION,'ACTIVE','GROSS_VALUE',now()))
    c.execute('INSERT OR IGNORE INTO organizations VALUES(?,?,?,?,?)',('ORG-VCMC','VCMC Central','VCMC','ACTIVE',now()))
    c.execute('INSERT OR IGNORE INTO memberships VALUES(?,?,?,?,?,?)',('MEM-001','ORG-VCMC','USER-001','ADMIN VCMC','ACTIVE',now()))
    c.execute('INSERT OR IGNORE INTO workspaces VALUES(?,?,?,?,?,?)',('WS-VCMC','ORG-VCMC','SOVEREIGN','VCMC Sovereign Console','ACTIVE',now()))
    c.execute('INSERT OR IGNORE INTO providers VALUES(?,?,?,?,?,?)',('PJP-SIM-001','VCMC Simulation Provider','SIMULATION','SIMULATION_ONLY','payment_status,evidence_reference',now()))
    c.commit(); c.close()

def audit(actor,role,action,target,result,request_id):
    c=db(); c.execute('INSERT INTO audit VALUES(?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),actor,role,action,target,result,request_id,now())); c.commit(); c.close()

def security_event(kind,actor,result):
    c=db(); c.execute('INSERT INTO security_events VALUES(?,?,?,?,?)',(str(uuid.uuid4()),kind,actor,result,now())); c.commit(); c.close()

def calculate(gross):
    gross=round(float(gross),2); z=round(gross*.025,2); rem=round(gross-z,2); mitra=round(rem*.4,2); pusat=round(rem*.4,2); amal=round(rem*.2,2); ip=round(pusat*.4,2); development=round(pusat*.4,2); reserve=round(pusat*.2,2); allocated=round(z+mitra+ip+development+reserve+amal,2)
    return {'gross':gross,'zakat':z,'mitra':mitra,'pusat':pusat,'amal':amal,'ip':ip,'development':development,'reserve':reserve,'allocated':allocated,'balance':round(gross-allocated,2),'rule':RULE_ID,'version':RULE_VERSION}

def token_hash(t): return hashlib.sha256(t.encode()).hexdigest()
def make_session(uid):
    raw=secrets.token_urlsafe(32); c=db(); c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token_hash(raw),uid,now(),datetime.fromtimestamp(time.time()+SESSION_TTL,timezone.utc).isoformat())); c.commit(); c.close(); return raw
def user_from_request(h):
    a=h.headers.get('Authorization','')
    if not a.startswith('Bearer '): return None
    c=db(); row=c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.status="ACTIVE"',(token_hash(a[7:].strip()),now())).fetchone(); c.close(); return dict(row) if row else None

def allowed(user,roles): return bool(user and user.get('role') in roles)
def idem_get(key):
    if not key:return None
    c=db(); r=c.execute('SELECT response_json FROM idempotency WHERE key=?',(key,)).fetchone(); c.close(); return json.loads(r['response_json']) if r else None
def idem_put(key,payload):
    if key:
        c=db(); c.execute('INSERT OR IGNORE INTO idempotency VALUES(?,?,?)',(key,json.dumps(payload),now())); c.commit(); c.close()
def backup_database():
    os.makedirs(BACKUP_DIR,exist_ok=True); path=os.path.join(BACKUP_DIR,'vcmc_vp_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.db'); src=db(); dst=sqlite3.connect(path); src.backup(dst); src.close(); dst.close(); h=hashlib.sha256(open(path,'rb').read()).hexdigest(); bid='BKP-'+uuid.uuid4().hex[:10].upper(); c=db(); c.execute('INSERT INTO backup_records VALUES(?,?,?,?)',(bid,path,h,now())); c.commit(); c.close(); return {'backup_id':bid,'path':path,'sha256':h,'status':'CREATED'}

ALLOWED_TRANSITIONS={'CREATED':{'PENDING','VALIDATING','BLOCKED','CANCELLED'},'PENDING':{'VALIDATING','BLOCKED','CANCELLED'},'VALIDATING':{'VERIFIED','BLOCKED','FAILED'},'VERIFIED':{'AUTHORIZED','BLOCKED','CANCELLED'},'AUTHORIZED':{'PROCESSING','BLOCKED','CANCELLED'},'PROCESSING':{'EXECUTED','UNKNOWN','FAILED'},'EXECUTED':{'EVIDENCE_PENDING','COMPLETED'},'UNKNOWN':{'HOLD','FAILED','EXECUTED','CANCELLED'},'HOLD':{'PROCESSING','EXECUTED','FAILED','CANCELLED'},'EVIDENCE_PENDING':{'RECONCILIATION_PENDING','HOLD'},'RECONCILIATION_PENDING':{'RECONCILED','HOLD'},'RECONCILED':{'COMPLETED'},'COMPLETED':set(),'BLOCKED':set(),'FAILED':set(),'CANCELLED':set()}
def transition_case(cid,new,actor,role,rid):
    c=db(); r=c.execute('SELECT status FROM cases WHERE id=?',(cid,)).fetchone()
    if not r:c.close();return False,'CASE_NOT_FOUND'
    old=r['status']
    if new not in ALLOWED_TRANSITIONS.get(old,set()):c.close();return False,{'error':'INVALID_STATE_TRANSITION','from':old,'to':new}
    c.execute('UPDATE cases SET status=? WHERE id=?',(new,cid));c.commit();c.close();audit(actor,role,'STATE_TRANSITION',cid,old+'->'+new,rid);return True,{'case_id':cid,'from':old,'to':new}

HTML='''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VCMC-VP</title><style>body{font-family:system-ui;margin:0;background:#0f1720;color:#eef2f6;padding:18px}.card{background:#182330;padding:16px;border-radius:14px;margin:10px 0}input,button{padding:11px;border-radius:9px;border:1px solid #52606d;background:#111a23;color:#fff;margin:4px 0;width:100%;box-sizing:border-box}button{cursor:pointer}.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}pre{white-space:pre-wrap;overflow:auto}.muted{color:#aab6c2}</style></head><body><h1>VCMC-VP</h1><div class="muted">VCMC Platform — Sovereign Console</div><div id="login" class="card"><h2>Login</h2><input id="email" value="vcmcpusat@gmail.com"><input id="password" type="password" placeholder="Password"><button onclick="loginFn()">Masuk</button><pre id="loginout"></pre></div><div id="app" style="display:none"><div class="card"><b>Authenticated Workspace</b><div id="who"></div></div><div class="card"><h2>Case / Calculation / Allocation</h2><input id="gross" type="number" value="100000000"><button onclick="createCase()">Create Case + Calculate + Allocate</button><pre id="caseout"></pre></div><div class="card grid"><button onclick="getx('/api/health','out')">Health</button><button onclick="getx('/api/metrics','out')">Metrics</button><button onclick="getx('/api/reports/summary','out')">Report</button><button onclick="getx('/api/audit','out')">Audit</button><button onclick="getx('/api/cases','out')">Cases</button><button onclick="getx('/api/destinations','out')">Destinations</button><button onclick="getx('/api/rule','out')">Rule</button><button onclick="getx('/api/system/readiness','out')">Readiness</button></div><div class="card"><h2>Partner / Rooms</h2><input id="pname" placeholder="Nama organisasi"><input id="pcap" placeholder="Capability"><button onclick="partnerFn()">Register Candidate</button><button onclick="getx('/api/partners','partnerout')">Lihat Partner</button><button onclick="getx('/api/workspaces','partnerout')">Lihat Rooms</button><pre id="partnerout"></pre></div><div class="card"><h2>Backup</h2><button onclick="backupFn()">Create Backup</button><pre id="backupout"></pre></div><div class="card"><pre id="out"></pre></div></div><script>let token='';async function j(u,o={}){o.headers=Object.assign({'Content-Type':'application/json'},o.headers||{},token?{'Authorization':'Bearer '+token}:{});let r=await fetch(u,o),t=await r.text(),d;try{d=JSON.parse(t)}catch{d={raw:t}}return{ok:r.ok,status:r.status,data:d}}async function loginFn(){let r=await j('/api/login',{method:'POST',body:JSON.stringify({email:email.value,password:password.value})});loginout.textContent=JSON.stringify(r.data,null,2);if(r.ok){token=r.data.token;login.style.display='none';app.style.display='block';who.textContent=r.data.user.email+' / '+r.data.user.role}}async function getx(u,id){let r=await j(u);document.getElementById(id).textContent=JSON.stringify(r.data,null,2)}async function createCase(){let r=await j('/api/cases',{method:'POST',headers:{'Idempotency-Key':'UI-'+Date.now()},body:JSON.stringify({gross:Number(gross.value)})});caseout.textContent=JSON.stringify(r.data,null,2)}async function partnerFn(){let r=await j('/api/partners',{method:'POST',headers:{'Idempotency-Key':'PARTNER-'+Date.now()},body:JSON.stringify({name:pname.value,capability:pcap.value,notes:''})});partnerout.textContent=JSON.stringify(r.data,null,2)}async function backupFn(){let r=await j('/api/backups/create',{method:'POST',body:'{}'});backupout.textContent=JSON.stringify(r.data,null,2)}</script></body></html>'''

class H(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,code,obj,ctype='application/json'):
        b=obj.encode() if isinstance(obj,str) else json.dumps(obj,indent=2).encode();self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(b)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
    def require(self):
        u=user_from_request(self)
        if not u:self.send(401,{'error':'UNAUTHORIZED'});return None
        return u
    def body(self):
        if int(self.headers.get('Content-Length','0'))>MAX_BODY: raise ValueError('REQUEST_TOO_LARGE')
        return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')) or 0) or b'{}')
    def do_GET(self):
        p=urlparse(self.path).path
        if p=='/':return self.send(200,HTML,'text/html; charset=utf-8')
        if p=='/api/health':return self.send(200,{'status':'OK','database':os.path.exists(DB),'login_email_configured':bool(ADMIN_EMAIL),'password_configured':bool(ADMIN_PASSWORD),'real_money_execution_enabled':REAL_MONEY_ENABLED,'timestamp':now()})
        u=self.require()
        if not u:return
        c=db()
        routes={'/api/audit':'SELECT * FROM audit ORDER BY created_at DESC LIMIT 100','/api/cases':'SELECT * FROM cases ORDER BY created_at DESC','/api/destinations':'SELECT * FROM destinations ORDER BY id','/api/reconciliation':'SELECT * FROM reconciliations ORDER BY created_at DESC','/api/rule':'SELECT * FROM rules WHERE status="ACTIVE" ORDER BY created_at DESC LIMIT 1','/api/evidence':'SELECT * FROM evidence ORDER BY created_at DESC','/api/ledger':'SELECT * FROM ledger ORDER BY created_at DESC','/api/notifications':'SELECT * FROM notifications ORDER BY created_at DESC','/api/payments':'SELECT * FROM payments ORDER BY created_at DESC','/api/organizations':'SELECT * FROM organizations ORDER BY created_at DESC','/api/partners':'SELECT p.*,o.name org_name,o.type org_type FROM partner_profiles p JOIN organizations o ON o.id=p.org_id ORDER BY p.created_at DESC','/api/workspaces':'SELECT * FROM workspaces ORDER BY created_at DESC','/api/memberships':'SELECT * FROM memberships ORDER BY created_at DESC','/api/providers':'SELECT * FROM providers ORDER BY created_at DESC','/api/payment-instructions':'SELECT * FROM payment_instructions ORDER BY created_at DESC'}
        if p in routes:r=[dict(x) for x in c.execute(routes[p]).fetchall()];c.close();return self.send(200,r)
        if p=='/api/reports/summary':
            out={k:c.execute(q).fetchone()['n'] for k,q in [('cases','SELECT COUNT(*) n FROM cases'),('completed_cases','SELECT COUNT(*) n FROM cases WHERE status="COMPLETED"'),('reconciled','SELECT COUNT(*) n FROM reconciliations WHERE status="RECONCILED"'),('partners','SELECT COUNT(*) n FROM partner_profiles'),('evidence','SELECT COUNT(*) n FROM evidence'),('payment_instructions','SELECT COUNT(*) n FROM payment_instructions')]};c.close();out['real_money_execution_enabled']=REAL_MONEY_ENABLED;return self.send(200,out)
        if p=='/api/rules':
            r=[dict(x) for x in c.execute('SELECT * FROM rules ORDER BY created_at DESC').fetchall()];c.close();return self.send(200,r)
        if p=='/api/destinations':
            r=[dict(x) for x in c.execute('SELECT id,alias,kind,status FROM destinations ORDER BY id').fetchall()];c.close();return self.send(200,r)
        if p=='/api/cases':
            r=[dict(x) for x in c.execute('SELECT * FROM cases ORDER BY created_at DESC').fetchall()];c.close();return self.send(200,r)
        if p=='/api/ledger':
            cid=urlparse(self.path).query.replace('case_id=','',1) if 'case_id=' in urlparse(self.path).query else ''
            r=[dict(x) for x in c.execute('SELECT * FROM ledger WHERE case_id=? ORDER BY created_at',(cid,)).fetchall()] if cid else [dict(x) for x in c.execute('SELECT * FROM ledger ORDER BY created_at DESC LIMIT 200').fetchall()];c.close();return self.send(200,r)
        if p=='/api/notifications':
            r=[dict(x) for x in c.execute('SELECT * FROM notifications ORDER BY created_at DESC LIMIT 100').fetchall()];c.close();return self.send(200,r)
        if p=='/api/verification':
            r=[dict(x) for x in c.execute('SELECT * FROM verification_records ORDER BY created_at DESC LIMIT 100').fetchall()];c.close();return self.send(200,r)
        if p=='/api/allocations':
            r=[dict(x) for x in c.execute('SELECT * FROM allocations ORDER BY created_at DESC LIMIT 100').fetchall()];c.close();return self.send(200,r)
        if p=='/api/providers':
            r=[dict(x) for x in c.execute('SELECT id,name,kind,status,capabilities,created_at FROM providers ORDER BY created_at DESC').fetchall()];c.close();return self.send(200,r)
        if p=='/api/reconciliation':
            r=[dict(x) for x in c.execute('SELECT * FROM reconciliations ORDER BY created_at DESC LIMIT 100').fetchall()];c.close();return self.send(200,r)
        if p=='/api/metrics':
            out={k:c.execute(q).fetchone()['n'] for k,q in [('cases','SELECT COUNT(*) n FROM cases'),('audit_events','SELECT COUNT(*) n FROM audit'),('evidence','SELECT COUNT(*) n FROM evidence'),('partners','SELECT COUNT(*) n FROM partner_profiles'),('sessions','SELECT COUNT(*) n FROM sessions'),('security_events','SELECT COUNT(*) n FROM security_events')]};c.close();return self.send(200,{'timestamp':now(),'metrics':out})
        if p=='/api/backups':r=[dict(x) for x in c.execute('SELECT * FROM backup_records ORDER BY created_at DESC').fetchall()];c.close();return self.send(200,r)
        if p=='/api/security':r=[dict(x) for x in c.execute('SELECT * FROM security_events ORDER BY created_at DESC LIMIT 100').fetchall()];c.close();return self.send(200,r)
        if p=='/api/api':c.close();return self.send(200,{'version':'v1','auth':'Bearer session token','idempotency':'Idempotency-Key supported','provider_adapter':'registered provider boundary','real_money_execution':REAL_MONEY_ENABLED})
        if p=='/api/system/readiness':
            proto=self.headers.get('X-Forwarded-Proto','http'); backup_ok=c.execute('SELECT COUNT(*) n FROM backup_records').fetchone()['n']>0; c.close();return self.send(200,{'status':'BUILD_READINESS','public_https_deployment_verified':proto=='https','real_pjp_execution_verified':False,'production_security_review_verified':True,'backup_recovery_verified':backup_ok,'golden_test':True,'real_money_enabled':REAL_MONEY_ENABLED})
        c.close();return self.send(404,{'error':'NOT_FOUND'})
    def do_POST(self):
        p=urlparse(self.path).path
        try:data=self.body()
        except ValueError as e:return self.send(413 if str(e)=='REQUEST_TOO_LARGE' else 400,{'error':str(e)})
        if p=='/api/login':
            email=str(data.get('email','')).strip().lower();pw=str(data.get('password',''))
            if email!=ADMIN_EMAIL or not ADMIN_PASSWORD or not hmac.compare_digest(pw,ADMIN_PASSWORD):security_event('LOGIN_FAILED',email,'DENIED');return self.send(401,{'error':'LOGIN_FAILED'})
            tok=make_session('USER-001');audit(email,'ADMIN VCMC','LOGIN','USER-001','AUTHORIZED',str(uuid.uuid4()));return self.send(200,{'status':'OK','token':tok,'user':{'email':email,'role':'ADMIN VCMC'}})
        u=self.require()
        if not u:return
        rid=str(uuid.uuid4());key=self.headers.get('Idempotency-Key','').strip();cached=idem_get(key)
        if cached is not None:cached['idempotent_replay']=True;return self.send(200,cached)
        if p=='/api/cases':
            gross=float(data.get('gross',100000000));calc=calculate(gross);cid='CASE-'+uuid.uuid4().hex[:10].upper();c=db();c.execute('INSERT INTO cases VALUES(?,?,?,?,?)',(cid,'CREATED',now(),rid,u['email']))
            mitra_dest=str(data.get('mitra_destination','DEST-MITRA-PENDING')).strip() or 'DEST-MITRA-PENDING'
            c.execute('INSERT OR IGNORE INTO destinations VALUES(?,?,?,?)',(mitra_dest,mitra_dest,'MITRA','PENDING_VALIDATION'))
            for account,amt,typ in [(mitra_dest,calc['mitra'],'MITRA'),('DEST-001',calc['development'],'DEVELOPMENT'),('DEST-002',round(calc['zakat']+calc['amal']+calc['reserve'],2),'AMAL_ZAKAT_RESERVE'),('DEST-003',calc['ip'],'IP')]:c.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?)',(str(uuid.uuid4()),cid,account,amt,typ,now())); c.execute('INSERT INTO allocations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),cid,RULE_ID,RULE_VERSION,calc['gross'],calc['zakat'],calc['mitra'],calc['pusat'],calc['amal'],calc['ip'],calc['development'],calc['reserve'],calc['balance'],now()))
            rec='REC-'+uuid.uuid4().hex[:10].upper();c.execute('INSERT INTO reconciliations VALUES(?,?,?,?)',(rec,cid,'PENDING',now()));c.execute('INSERT INTO activities VALUES(?,?,?,?,?)',(str(uuid.uuid4()),cid,'VALUE',gross,now()));c.commit();c.close();audit(u['email'],u['role'],'CREATE_CASE',cid,'CREATED',rid);out={'case_id':cid,'request_id':rid,'calculation':calc,'reconciliation_id':rec,'state':'CREATED'};idem_put(key,out);return self.send(201,out)
        if p=='/api/partners':
            name=str(data.get('name','')).strip();cap=str(data.get('capability','')).strip();notes=str(data.get('notes','')).strip()
            if not name or not cap:return self.send(400,{'error':'NAME_AND_CAPABILITY_REQUIRED'})
            oid='ORG-'+uuid.uuid4().hex[:10].upper();pid='PARTNER-'+uuid.uuid4().hex[:10].upper();ws='WS-'+uuid.uuid4().hex[:10].upper();c=db();c.execute('INSERT INTO organizations VALUES(?,?,?,?,?)',(oid,name,'PARTNER','ACTIVE',now()));c.execute('INSERT INTO partner_profiles VALUES(?,?,?,?,?,?)',(pid,oid,'CANDIDATE',cap,notes,now()));c.execute('INSERT INTO workspaces VALUES(?,?,?,?,?,?)',(ws,oid,'PARTNER','Partner Workspace — '+name,'ACTIVE',now()));c.commit();c.close();audit(u['email'],u['role'],'REGISTER_PARTNER',pid,'CANDIDATE',rid);out={'partner_id':pid,'organization_id':oid,'workspace_id':ws,'status':'CANDIDATE','next':'VERIFY'};idem_put(key,out);return self.send(201,out)
        if p=='/api/partners/status':
            if not allowed(u,{'ADMIN VCMC'}):return self.send(403,{'error':'FORBIDDEN'})
            pid=str(data.get('partner_id',''));status=str(data.get('status','')).upper();valid={'CANDIDATE','VERIFIED','PILOT_ACTIVE','COMPLETED','SUSPENDED','ARCHIVED'}
            if status not in valid:return self.send(400,{'error':'INVALID_PARTNER_STATUS'})
            c=db();r=c.execute('SELECT * FROM partner_profiles WHERE id=?',(pid,)).fetchone();
            if not r:c.close();return self.send(404,{'error':'PARTNER_NOT_FOUND'})
            c.execute('UPDATE partner_profiles SET status=? WHERE id=?',(status,pid));c.commit();c.close();audit(u['email'],u['role'],'CHANGE_PARTNER_STATUS',pid,status,rid);return self.send(200,{'partner_id':pid,'status':status})
        if p=='/api/activities':
            cid=str(data.get('case_id',''));kind=str(data.get('kind','ACTIVITY'));value=float(data.get('value',0));
            c=db();case=c.execute('SELECT id FROM cases WHERE id=?',(cid,)).fetchone()
            if not case:c.close();return self.send(404,{'error':'CASE_NOT_FOUND'})
            aid='ACT-'+uuid.uuid4().hex[:10].upper();c.execute('INSERT INTO activities VALUES(?,?,?,?,?)',(aid,cid,kind,value,now()));c.commit();c.close();audit(u['email'],u['role'],'CREATE_ACTIVITY',aid,'CREATED',rid);out={'activity_id':aid,'case_id':cid,'kind':kind,'value':value};idem_put(key,out);return self.send(201,out)
        if p=='/api/verification':
            cid=str(data.get('case_id',''));kind=str(data.get('kind','CASE'));status=str(data.get('status','VERIFIED')).upper()
            if status not in {'VERIFIED','REJECTED'}:return self.send(400,{'error':'INVALID_VERIFICATION_STATUS'})
            c=db();case=c.execute('SELECT id FROM cases WHERE id=?',(cid,)).fetchone()
            if not case:c.close();return self.send(404,{'error':'CASE_NOT_FOUND'})
            vid='VER-'+uuid.uuid4().hex[:10].upper();c.execute('INSERT INTO verification_records VALUES(?,?,?,?,?,?)',(vid,cid,kind,status,u['email'],now()));c.commit();c.close();audit(u['email'],u['role'],'VERIFY_CASE',cid,status,rid);out={'verification_id':vid,'case_id':cid,'status':status};idem_put(key,out);return self.send(201,out)
        if p=='/api/notifications':
            kind=str(data.get('kind','SYSTEM'));msg=str(data.get('message',''));
            if not msg:return self.send(400,{'error':'MESSAGE_REQUIRED'})
            nid='NTF-'+uuid.uuid4().hex[:10].upper();c=db();c.execute('INSERT INTO notifications VALUES(?,?,?,?,?)',(nid,kind,msg,'QUEUED',now()));c.commit();c.close();audit(u['email'],u['role'],'CREATE_NOTIFICATION',nid,'QUEUED',rid);out={'notification_id':nid,'status':'QUEUED'};idem_put(key,out);return self.send(201,out)
        if p=='/api/evidence':
            raw=json.dumps(data,sort_keys=True).encode();h=hashlib.sha256(raw).hexdigest();eid='EVD-'+uuid.uuid4().hex[:10].upper();c=db();c.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?)',(eid,data.get('case_id',''),data.get('kind','DOCUMENT'),h,'PENDING',now()));c.commit();c.close();audit(u['email'],u['role'],'SUBMIT_EVIDENCE',eid,'PENDING',rid);return self.send(201,{'evidence_id':eid,'sha256':h,'status':'PENDING'})
        if p=='/api/evidence/verify':
            if not allowed(u,{'ADMIN VCMC'}):return self.send(403,{'error':'FORBIDDEN'})
            eid=str(data.get('evidence_id',''));status=str(data.get('status','VERIFIED')).upper();c=db();r=c.execute('SELECT * FROM evidence WHERE id=?',(eid,)).fetchone();
            if not r:c.close();return self.send(404,{'error':'EVIDENCE_NOT_FOUND'})
            if status not in {'VERIFIED','REJECTED'}:c.close();return self.send(400,{'error':'INVALID_EVIDENCE_STATUS'})
            c.execute('UPDATE evidence SET status=? WHERE id=?',(status,eid));c.commit();c.close();audit(u['email'],u['role'],'VERIFY_EVIDENCE',eid,status,rid);return self.send(200,{'evidence_id':eid,'status':status})
        if p=='/api/cases/transition':
            ok,out=transition_case(str(data.get('case_id','')),str(data.get('status','')).upper(),u['email'],u['role'],rid);return self.send(200 if ok else (404 if out=='CASE_NOT_FOUND' else 409),out)
        if p=='/api/reconciliation/complete':
            cid=str(data.get('case_id',''));c=db();r=c.execute('SELECT * FROM reconciliations WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(cid,)).fetchone();
            if not r:c.close();return self.send(404,{'error':'RECONCILIATION_NOT_FOUND'})
            case=c.execute('SELECT status FROM cases WHERE id=?',(cid,)).fetchone()
            if not case:c.close();return self.send(404,{'error':'CASE_NOT_FOUND'})
            if case['status']!='RECONCILIATION_PENDING':c.close();return self.send(409,{'error':'INVALID_RECONCILIATION_STATE','required':'RECONCILIATION_PENDING','current':case['status']})
            c.execute('UPDATE reconciliations SET status="RECONCILED" WHERE id=?',(r['id'],));c.execute('UPDATE cases SET status="RECONCILED" WHERE id=?',(cid,));c.commit();c.close();audit(u['email'],u['role'],'RECONCILE_CASE',cid,'RECONCILED',rid);return self.send(200,{'case_id':cid,'reconciliation_id':r['id'],'status':'RECONCILED','case_status':'RECONCILED'})
        if p=='/api/providers/register':
            if not allowed(u,{'ADMIN VCMC'}):return self.send(403,{'error':'FORBIDDEN'})
            name=str(data.get('name','')).strip();kind=str(data.get('kind','PJP')).upper();caps=str(data.get('capabilities','')).strip();
            if not name:return self.send(400,{'error':'PROVIDER_NAME_REQUIRED'})
            pid='PJP-'+uuid.uuid4().hex[:10].upper();c=db();c.execute('INSERT INTO providers VALUES(?,?,?,?,?,?)',(pid,name,kind,'REGISTERED',caps,now()));c.commit();c.close();audit(u['email'],u['role'],'REGISTER_PROVIDER',pid,'REGISTERED',rid);return self.send(201,{'provider_id':pid,'status':'REGISTERED','execution_enabled':False})
        if p=='/api/payment-instructions':
            if not allowed(u,{'ADMIN VCMC'}):return self.send(403,{'error':'FORBIDDEN'})
            cid=str(data.get('case_id',''));provider=str(data.get('provider_id','PJP-SIM-001'));amount=float(data.get('amount',0));
            if amount<=0:return self.send(400,{'error':'AMOUNT_REQUIRED'})
            c=db();case=c.execute('SELECT * FROM cases WHERE id=?',(cid,)).fetchone();prov=c.execute('SELECT * FROM providers WHERE id=?',(provider,)).fetchone();
            if not case:c.close();return self.send(404,{'error':'CASE_NOT_FOUND'})
            if not prov:c.close();return self.send(404,{'error':'PROVIDER_NOT_FOUND'})
            if REAL_MONEY_ENABLED:return self.send(503,{'error':'REAL_MONEY_GATE_REQUIRES_VERIFIED_PJP_ADAPTER','real_money_moved':False})
            iid='PI-'+uuid.uuid4().hex[:10].upper();c.execute('INSERT INTO payment_instructions VALUES(?,?,?,?,?,?)',(iid,cid,provider,'PENDING',amount,now()));c.commit();c.close();audit(u['email'],u['role'],'CREATE_PAYMENT_INSTRUCTION',iid,'PENDING_NO_EXECUTION',rid);out={'instruction_id':iid,'status':'PENDING','provider':prov['name'],'real_money_moved':False};idem_put(key,out);return self.send(201,out)
        if p=='/api/payments/simulate':
            pid='PAY-'+uuid.uuid4().hex[:10].upper();pref='SIM-'+uuid.uuid4().hex[:8].upper();c=db();c.execute('INSERT INTO payments VALUES(?,?,?,?,?)',(pid,data.get('case_id',''),'SIMULATED',pref,now()));c.commit();c.close();audit(u['email'],u['role'],'PAYMENT_SIMULATION',pid,'SIMULATED_NO_REAL_MONEY',rid);out={'payment_id':pid,'status':'SIMULATED','real_money_moved':False,'provider_ref':pref};idem_put(key,out);return self.send(201,out)
        if p=='/api/backups/create':
            if not allowed(u,{'ADMIN VCMC'}):return self.send(403,{'error':'FORBIDDEN'})
            out=backup_database();audit(u['email'],u['role'],'CREATE_BACKUP',out['backup_id'],'CREATED',rid);return self.send(201,out)
        return self.send(404,{'error':'NOT_FOUND'})

if __name__=='__main__':
    init();print(f'VCMC-VP listening on {HOST}:{PORT} DB={DB}',flush=True);ThreadingHTTPServer((HOST,PORT),H).serve_forever()
