import os, json, sqlite3, hashlib, secrets, shutil, time, base64, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, urlencode, parse_qs
from datetime import datetime, timezone
DB=os.getenv('VCMC_DB','vcmp.db'); HOST=os.getenv('HOST','0.0.0.0'); PORT=int(os.getenv('PORT','10000'))
ADMIN_EMAIL=os.getenv('VCMC_ADMIN_EMAIL',''); ADMIN_PASSWORD=os.getenv('VCMC_ADMIN_PASSWORD',''); PUBLIC_BASE_URL=os.getenv('PUBLIC_BASE_URL','').rstrip('/')
HF_OAUTH_STATES={}
REAL_MONEY=os.getenv('VCMC_REAL_MONEY_ENABLED','false').lower()=='true'; BACKUP_DIR=os.getenv('VCMC_BACKUP_DIR','backups')
RULE_ID='VCMC-ALLOC-001'; RULE_VERSION='1.0.0'; FORMULA_VERSION='1.0.0'
def now(): return datetime.now(timezone.utc).isoformat()
def conn():
 c=sqlite3.connect(DB,check_same_thread=False); c.row_factory=sqlite3.Row; return c
def init():
 if not ADMIN_EMAIL or not ADMIN_PASSWORD: raise RuntimeError('VCMC_ADMIN_EMAIL and VCMC_ADMIN_PASSWORD must be set')
 c=conn(); c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,login_id TEXT UNIQUE,password_hash TEXT,role TEXT,status TEXT DEFAULT 'PUBLIC',name TEXT,oauth_provider TEXT,oauth_sub TEXT); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER,expires REAL,context TEXT DEFAULT 'PUBLIC'); CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,state TEXT,gross INTEGER,created_at TEXT); CREATE TABLE IF NOT EXISTS case_events(id INTEGER PRIMARY KEY,case_id TEXT,state TEXT,at TEXT,actor TEXT); CREATE TABLE IF NOT EXISTS payment_instructions(id INTEGER PRIMARY KEY,case_id TEXT,provider_id TEXT,status TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,case_id TEXT,amount INTEGER,kind TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS allocations(id INTEGER PRIMARY KEY,case_id TEXT,dest TEXT,amount INTEGER,kind TEXT); CREATE TABLE IF NOT EXISTS destinations(id TEXT PRIMARY KEY,label TEXT,kind TEXT,active INTEGER); CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY,case_id TEXT,kind TEXT,sha256 TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS reconciliations(id INTEGER PRIMARY KEY,case_id TEXT,status TEXT,expected INTEGER,executed INTEGER,received INTEGER,ledger INTEGER,created_at TEXT); CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at TEXT,actor TEXT,action TEXT,entity TEXT,details TEXT); CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY,response TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS backups(id INTEGER PRIMARY KEY,path TEXT,sha256 TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS providers(id TEXT PRIMARY KEY,name TEXT,execution_verified INTEGER); CREATE TABLE IF NOT EXISTS partners(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,contact TEXT,created_at TEXT,updated_at TEXT); CREATE TABLE IF NOT EXISTS pilots(id TEXT PRIMARY KEY,name TEXT NOT NULL,partner_id TEXT,status TEXT NOT NULL,objective TEXT,created_at TEXT,updated_at TEXT); CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,pilot_id TEXT,created_at TEXT,updated_at TEXT); CREATE TABLE IF NOT EXISTS directions(id TEXT PRIMARY KEY,name TEXT NOT NULL,priority TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT,updated_at TEXT); CREATE TABLE IF NOT EXISTS capital_plans(id TEXT PRIMARY KEY,name TEXT NOT NULL,purpose TEXT NOT NULL,status TEXT NOT NULL,amount INTEGER NOT NULL,created_at TEXT,updated_at TEXT); CREATE TABLE IF NOT EXISTS partner_access_requests(id TEXT PRIMARY KEY,request_type TEXT NOT NULL,name TEXT NOT NULL,organization TEXT,country TEXT,contact_type TEXT,contact_value TEXT,language TEXT NOT NULL,message TEXT,status TEXT NOT NULL,created_at TEXT,updated_at TEXT); CREATE TABLE IF NOT EXISTS access_activations(code TEXT PRIMARY KEY,request_id TEXT NOT NULL,email TEXT NOT NULL,role TEXT NOT NULL,expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);''')
 try: c.execute('ALTER TABLE users ADD COLUMN login_id TEXT')
 except sqlite3.OperationalError: pass
 c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_login_id ON users(login_id) WHERE login_id IS NOT NULL')
 try: c.execute('ALTER TABLE users ADD COLUMN oauth_provider TEXT')
 except sqlite3.OperationalError: pass
 try: c.execute('ALTER TABLE users ADD COLUMN oauth_sub TEXT')
 except sqlite3.OperationalError: pass
 c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_oauth ON users(oauth_provider,oauth_sub) WHERE oauth_provider IS NOT NULL AND oauth_sub IS NOT NULL')
 try: c.execute("ALTER TABLE sessions ADD COLUMN context TEXT DEFAULT 'PUBLIC'")
 except sqlite3.OperationalError: pass
 try: c.execute('ALTER TABLE users ADD COLUMN name TEXT')
 except sqlite3.OperationalError: pass
 try: c.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'PUBLIC'")
 except sqlite3.OperationalError: pass
 c.execute("UPDATE users SET status='CREATOR' WHERE role='SOVEREIGN' AND (status IS NULL OR status='PUBLIC')")
 c.execute("UPDATE users SET name='VCMC Sovereign' WHERE email=? AND (name IS NULL OR name='')",(ADMIN_EMAIL,))
 admin=c.execute('SELECT * FROM users WHERE email=?',(ADMIN_EMAIL,)).fetchone()
 if not admin:
  c.execute('INSERT INTO users(email,login_id,password_hash,role,status,name) VALUES(?,?,?,?,?,?)',(ADMIN_EMAIL,'SOVEREIGN',hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest(),'SOVEREIGN','CREATOR','VCMC Sovereign'))
 else:
  if not admin['login_id']: c.execute('UPDATE users SET login_id=? WHERE id=?',('SOVEREIGN',admin['id']))
 for row in [('DEST-001','MODAL_PENGEMBANGAN','CAPITAL'),('DEST-002','AMAL_ZAKAT_RESERVE','AMAL_ZAKAT_RESERVE'),('DEST-003','HAK_CIPTA_IP','IP')]: c.execute('INSERT OR IGNORE INTO destinations VALUES(?,?,?,1)',row)
 c.execute("INSERT OR IGNORE INTO providers VALUES('PJP-SIM-001','Simulation Provider',0)")
 c.commit(); c.close()
def calc(g):
 g=int(g); z=g*25//1000; r=g-z; m=r*40//100; p=r*40//100; a=r-m-p; ip=p*40//100; dev=p*40//100; reserve=p-ip-dev
 return {'gross':g,'zakat':z,'mitra':m,'pusat':p,'amal':a,'ip':ip,'development':dev,'reserve':reserve,'formula_version':FORMULA_VERSION}
def audit(actor,action,entity,details=''):
 c=conn(); c.execute('INSERT INTO audit(at,actor,action,entity,details) VALUES(?,?,?,?,?)',(now(),actor,action,entity,details)); c.commit(); c.close()
def external_role(status):
 return 'PARTNER' if status=='PARTNER' else 'CANDIDATE'
def issue_activation(c,request_id,email,role):
 c.execute('DELETE FROM access_activations WHERE request_id=? AND used=0',(request_id,))
 code='ACT-'+secrets.token_urlsafe(18); c.execute('INSERT INTO access_activations(code,request_id,email,role,expires,used,created_at) VALUES(?,?,?,?,?,?,?)',(code,request_id,email,role,time.time()+7*86400,0,now())); return code
class H(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def sendj(self,code,obj):
  b=json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
 def body(self): return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
 def auth(self):
  auth=self.headers.get('Authorization','').strip()
  t=auth[7:].strip() if auth.lower().startswith('bearer ') else ''
  c=conn()
  r=c.execute('SELECT u.*,s.context AS session_context FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(t,time.time())).fetchone() if t else None
  if not r:
   ck=self.headers.get('Cookie','')
   for part in ck.split(';'):
    if part.strip().startswith('vcmc_token='):
     t=part.strip().split('=',1)[1]
     r=c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(t,time.time())).fetchone()
     if r: break
  c.close(); return dict(r) if r else None
 def base_url(self):
  if PUBLIC_BASE_URL: return PUBLIC_BASE_URL
  proto=self.headers.get('X-Forwarded-Proto','').split(',')[0].strip() or ('https' if self.headers.get('Host','').endswith('.rollout.click') else 'http')
  return proto+'://'+self.headers.get('Host','localhost')
 def send_html(self,code,html,cookie=None):
  b=html.encode(); self.send_response(code); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store')
  if cookie: self.send_header('Set-Cookie',cookie)
  self.end_headers(); self.wfile.write(b)
 def hf_oauth_start(self):
  base=self.base_url(); client_id=base+'/.well-known/oauth-cimd'; redirect_uri=base+'/oauth/callback/huggingface'
  state=secrets.token_urlsafe(32); verifier=secrets.token_urlsafe(64)
  challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
  HF_OAUTH_STATES[state]={'verifier':verifier,'created':time.time()}
  q=urlencode({'client_id':client_id,'redirect_uri':redirect_uri,'response_type':'code','scope':'openid profile email','state':state,'code_challenge':challenge,'code_challenge_method':'S256'})
  self.send_response(302); self.send_header('Location','https://huggingface.co/oauth/authorize?'+q); self.send_header('Cache-Control','no-store'); self.end_headers()
 def hf_oauth_callback(self):
  params=parse_qs(urlparse(self.path).query); state=params.get('state',[''])[0]; code=params.get('code',[''])[0]
  if params.get('error'): return self.send_html(400,'<h2>Hugging Face login dibatalkan.</h2><p>Silakan kembali ke VCMC-VP dan coba lagi.</p>')
  saved=HF_OAUTH_STATES.pop(state,None)
  if not state or not code or not saved or time.time()-saved['created']>600: return self.send_html(400,'<h2>Login Hugging Face tidak valid.</h2><p>State OAuth tidak valid atau sudah kedaluwarsa.</p>')
  base=self.base_url(); client_id=base+'/.well-known/oauth-cimd'; redirect_uri=base+'/oauth/callback/huggingface'
  form=urlencode({'grant_type':'authorization_code','client_id':client_id,'code':code,'code_verifier':saved['verifier'],'redirect_uri':redirect_uri}).encode()
  try:
   req=urllib.request.Request('https://huggingface.co/oauth/token',data=form,headers={'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=20) as resp: tok=json.loads(resp.read().decode())
   access_token=tok.get('access_token','')
   if not access_token: raise ValueError('missing_access_token')
   req=urllib.request.Request('https://huggingface.co/oauth/userinfo',headers={'Authorization':'Bearer '+access_token,'Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=20) as resp: info=json.loads(resp.read().decode())
  except Exception:
   return self.send_html(502,'<h2>Login Hugging Face belum dapat diselesaikan.</h2><p>VCMC-VP tidak dapat memverifikasi sesi Hugging Face saat ini.</p>')
  sub=str(info.get('sub') or '').strip(); username=str(info.get('preferred_username') or info.get('name') or '').strip(); email=str(info.get('email') or '').strip().lower(); email_verified=bool(info.get('email_verified')); name=username or email or 'Hugging Face user'
  if not sub: return self.send_html(502,'<h2>Identitas Hugging Face tidak lengkap.</h2><p>Login ditahan.</p>')
  c=conn(); u=c.execute('SELECT * FROM users WHERE oauth_provider=? AND oauth_sub=?',('huggingface',sub)).fetchone()
  if not u and email and email_verified: u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
  if u and u['role']=='SOVEREIGN' and not (u['oauth_provider']=='huggingface' and u['oauth_sub']==sub): u=None
  if not u:
   safe_email=email if email and email_verified and not c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone() else 'hf+'+sub[:24]+'@oauth.vcmc.local'
   login_id='HF-'+sub[:16].upper()
   c.execute('INSERT INTO users(email,login_id,password_hash,role,status,name,oauth_provider,oauth_sub) VALUES(?,?,?,?,?,?,?,?)',(safe_email,login_id,'','PUBLIC','PUBLIC',name,'huggingface',sub))
   u=c.execute('SELECT * FROM users WHERE oauth_provider=? AND oauth_sub=?',('huggingface',sub)).fetchone()
  else:
   c.execute('UPDATE users SET name=?,oauth_provider=?,oauth_sub=? WHERE id=?',(name,'huggingface',sub,u['id']))
  tok2=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions(token,user_id,expires,context) VALUES(?,?,?,?)',(tok2,u['id'],time.time()+86400,'PUBLIC')); c.commit(); c.close()
  audit(u['email'],'LOGIN_HUGGINGFACE','USER',username or sub)
  self.send_response(303); self.send_header('Set-Cookie','vcmc_token='+tok2+'; Path=/; HttpOnly; Secure; SameSite=Lax'); self.send_header('Location','/'); self.end_headers()
 def do_GET(self):
  p=urlparse(self.path).path
  if p=='/.well-known/oauth-cimd':
   base=self.base_url(); return self.sendj(200,{'client_id':base+'/.well-known/oauth-cimd','client_name':'VCMC-VP','redirect_uris':[base+'/oauth/callback/huggingface'],'token_endpoint_auth_method':'none','client_uri':base})
  if p=='/oauth/login/huggingface': return self.hf_oauth_start()
  if p=='/oauth/callback/huggingface': return self.hf_oauth_callback()
  if p=='/':
   html='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#071b2b"><title>VCMC-VP</title><style>
:root{--bg:#07111f;--panel:#0b1728;--panel2:#101f36;--line:rgba(201,164,92,.20);--text:#f7f9ff;--muted:#b8c0cc;--accent:#c9a45c;--accent2:#e4c987;--warn:#e4c987}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:radial-gradient(circle at 15% 0%,#102b4a 0,#07111f 46%,#030914 100%);color:var(--text);min-height:100vh}button,input{font:inherit}main{max-width:900px;margin:auto;padding:0 16px 92px}.hidden{display:none!important}
.top{padding:20px 0 12px;display:flex;align-items:center;justify-content:space-between}.brand{display:flex;gap:12px;align-items:center}.mark{width:42px;height:42px;border-radius:14px;background:linear-gradient(145deg,#e4c987,#9f7b32);display:grid;place-items:center;color:#071225;font-weight:900}.eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}h1,h2,h3,p{margin:0}.muted{color:var(--muted)}.card{background:linear-gradient(145deg,rgba(16,31,59,.97),rgba(7,18,37,.97));border:1px solid var(--line);border-radius:22px;padding:18px;margin:12px 0;box-shadow:0 14px 34px rgba(0,0,0,.28)}.login{max-width:520px;margin:10vh auto}.input{width:100%;padding:14px 15px;margin:7px 0;border:1px solid var(--line);border-radius:13px;background:#0b1730;color:var(--text);outline:none}.primary{width:100%;padding:14px;border:0;border-radius:13px;background:var(--accent);color:#05202a;font-weight:800;margin-top:8px}.logout{border:1px solid var(--line);background:transparent;color:var(--text);padding:9px 12px;border-radius:11px}.hero{padding:20px;background:linear-gradient(135deg,rgba(212,175,55,.10),rgba(16,31,59,.96));}.identity{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.pill{display:inline-block;padding:6px 9px;border-radius:999px;background:rgba(212,175,55,.12);color:var(--accent);font-size:12px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.tile{padding:15px;border:1px solid var(--line);border-radius:17px;background:rgba(255,255,255,.035);min-height:72px}.tile b{display:block;margin-bottom:5px}.sectionhead{display:flex;justify-content:space-between;align-items:center;margin:22px 2px 8px}.sectionhead span{font-size:12px;color:var(--muted)}.rooms{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.room{padding:16px;border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.035);cursor:pointer}.room small{color:var(--muted)}.actions{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.action{border:1px solid var(--line);background:rgba(255,255,255,.04);color:var(--text);border-radius:16px;padding:14px;text-align:left}.feed{display:grid;gap:9px}.feeditem{padding:12px 14px;border-left:3px solid var(--accent);background:rgba(255,255,255,.035);border-radius:10px}.attention{border-left-color:var(--warn)}nav{position:fixed;z-index:10;bottom:0;left:0;right:0;background:rgba(4,16,24,.96);border-top:1px solid var(--line);padding:8px max(10px,calc((100vw - 900px)/2));display:grid;grid-template-columns:repeat(5,1fr);gap:4px}nav button{border:0;background:transparent;color:var(--muted);padding:8px 3px;font-size:11px}nav button.active{color:var(--accent)}.screen{min-height:70vh}.back{border:0;background:transparent;color:var(--accent);padding:0}.detail{line-height:1.55}.empty{padding:28px;text-align:center;color:var(--muted)}.password-wrap{position:relative}.password-wrap .input{width:100%;padding-right:48px}.password-toggle{position:absolute;right:6px;top:50%;transform:translateY(-50%);width:44px;height:44px;z-index:20;pointer-events:auto;touch-action:manipulation;border:0;background:transparent;color:var(--muted);cursor:pointer;border-radius:8px;display:grid;place-items:center}.password-toggle:hover,.password-toggle:focus{color:var(--text);background:rgba(255,255,255,.06);outline:none}.password-toggle svg{width:20px;height:20px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}@media(min-width:700px){.grid,.rooms{grid-template-columns:repeat(4,1fr)}.actions{grid-template-columns:repeat(4,1fr)}}
</style></head><body><main>
<section id="login" class="login"><div class="top"><div class="brand"><div class="mark">V</div><div><div class="eyebrow">Universal Global Development Architecture</div><h1>VCMC-VP</h1><div class="muted">Public Global Partner Gateway</div></div></div></div><div class="card hero"><div class="eyebrow">GLOBAL PUBLIC ENTRANCE</div><h2 style="margin:5px 0 8px">Masuk ke jaringan VCMC</h2><p class="muted">Pintu publik terbuka. Email bukan satu-satunya cara identifikasi.</p><div id="public-presence" class="pill" style="margin-top:10px">LIVE NOW · memuat...</div><div class="actions" style="margin-top:14px"><button type="button" id="public-open" class="action" onclick="window.showPublicLane('open')"><b>Public / Independent</b><br><span class="muted">Ajukan akses atau peluang secara mandiri.</span></button><button type="button" id="public-invited" class="action" onclick="window.showPublicLane('invited')"><b>Invited / Existing Partner</b><br><span class="muted">Gunakan undangan atau hubungan yang sudah ada.</span></button><button type="button" id="public-register" class="action" onclick="window.showRegisterLane()"><b>Buat Identitas VCMC</b><br><span class="muted">Daftar mandiri sebagai Candidate.</span></button></div><div id="public-lane" style="margin-top:14px"></div></div><div class="card"><p class="muted" style="margin-bottom:10px">VCMC internal access</p><form id="login-form" method="post" action="/api/login"><select id="context" name="context" class="input" aria-label="Konteks masuk"><option value="PUBLIC">Public / Explore</option><option value="INDIVIDUAL">Individual</option><option value="PROFESSIONAL">Professional</option><option value="ENTREPRENEUR">Entrepreneur / Business</option><option value="ORGANIZATION">Organization</option><option value="CANDIDATE">Candidate</option><option value="PARTNER">Partner</option><option value="CREATOR">Creator / Pusat</option></select><input id="email" name="email" class="input" type="text" placeholder="Email / Login ID" autocomplete="username"><div class="password-wrap"><input id="password" name="password" class="input" type="password" placeholder="Password" autocomplete="current-password"><button type="button" id="password-toggle" class="password-toggle" onpointerdown="window.togglePassword();event.preventDefault()" aria-label="Tampilkan password" title="Tampilkan password"><svg id="password-eye" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"></path><circle cx="12" cy="12" r="2.5"></circle></svg></button></div><button type="submit" id="login-button" class="primary" onclick="event.preventDefault();window.login()">Masuk ke VCMC-VP</button><a href="/oauth/login/huggingface" class="action" style="display:block;text-decoration:none;text-align:center;margin-top:10px"><b>Masuk dengan Hugging Face</b><br><span class="muted">Gunakan akun Hugging Face yang sudah kamu miliki.</span></a><div id="msg" class="muted" style="margin-top:10px"></div></form></div></section>
<section id="app" class="hidden"><header class="top"><div class="brand"><div class="mark">V</div><div><div class="eyebrow">VCMC-VP</div><h1 id="title">Home</h1></div></div><button class="logout" onclick="logout()">Keluar</button></header><div id="content" class="screen"></div></section>
</main><nav id="nav" class="hidden"><button data-tab="home" onclick="go('home')">⌂<br>Home</button><button data-tab="network" onclick="go(\'network\')">◉<br>Network</button><button data-tab="explore" onclick="go(\'explore\')">▦<br>Explore</button><button data-tab="evidence" onclick="go(\'evidence\')">✓<br>Evidence</button><button data-tab="profile" onclick="go(\'profile\')">◯<br>Profile</button></nav>
<script>
(function(){
  function toggle(){
    var p=document.getElementById('password'),e=document.getElementById('password-eye');
    if(!p)return;
    var show=p.type==='password';p.type=show?'text':'password';
    if(e)e.innerHTML=show?'<path d="M3 3l18 18"></path><path d="M10.6 6.2A10.8 10.8 0 0 1 12 6c6.5 0 10 6 10 6a18 18 0 0 1-4 4.2M6.2 6.8C3.4 8.4 2 12 2 12s3.5 6 10 6c1.5 0 2.8-.3 4-.8"></path><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"></path>':'<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"></path><circle cx="12" cy="12" r="2.5"></circle>';
  }
  async function loginFallback(){
    var m=document.getElementById('msg'),e=document.getElementById('email'),p=document.getElementById('password');
    if(m)m.textContent='Memverifikasi identitas...';
    try{
      var r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e?e.value:'',password:p?p.value:'',context:(document.getElementById('context')||{}).value||'PUBLIC'})});
      var d=await r.json();
      if(!r.ok){if(m)m.textContent=d.error==='unauthorized'?'Email atau password tidak cocok.':'Login gagal.';return;}
      try{sessionStorage.setItem('vcmc_token',d.token)}catch(_){}
      var l=document.getElementById('login'),a=document.getElementById('app'),n=document.getElementById('nav');
      if(l)l.classList.add('hidden');if(a)a.classList.remove('hidden');if(n)n.classList.remove('hidden');
      if(window.boot) return window.boot();
      var c=document.getElementById('content'),t=document.getElementById('title');
      if(t)t.textContent='Home';
      if(c)c.innerHTML='<div class="card hero"><h2>Selamat datang di VCMC-VP</h2><p class="muted">Session active · <span id="session-role">SOVEREIGN</span> · context: <span id="session-context">CREATOR / PUSAT</span></p></div>';
    }catch(_){if(m)m.textContent='Koneksi gagal.'}
  }
  window.__vcmcBootstrapLogin=loginFallback;
  window.__vcmcBootstrapToggle=toggle;
  document.addEventListener('click',function(ev){
    var t=ev.target.closest && ev.target.closest('#password-toggle,#login-button');
    if(!t)return;
    if(t.id==='password-toggle'){ev.preventDefault();toggle();}
    if(t.id==='login-button'){ev.preventDefault();loginFallback();}
  },true);
  document.addEventListener('submit',function(ev){
    if(ev.target && ev.target.id==='login-form'){ev.preventDefault();loginFallback();}
  },true);
})();
</script>
<script>
async function loadPublicPresence(){try{const r=await fetch('/api/public/presence',{cache:'no-store'});const d=await r.json();const el=document.getElementById('public-presence');if(el&&r.ok)el.textContent='LIVE NOW · '+d.live_now+' · '+d.registered_users+' registered';}catch(e){}}
loadPublicPresence();setInterval(loadPublicPresence,15000);
function showRegisterLane(){const box=document.getElementById('public-lane');box.innerHTML='<div class="card" style="margin:0"><div class="sectionhead"><h3>Buat Identitas VCMC</h3><button type="button" class="back" data-public-close>Tutup</button></div><p class="muted" style="margin-bottom:10px">Registrasi membuat identitas dan akun Candidate. Registration ≠ Approval ≠ Partner.</p><input id="reg-name" class="input" placeholder="Nama / Name" autocomplete="name"><select id="reg-context" class="input" aria-label="Konteks registrasi"><option value="CANDIDATE">Candidate / opportunity</option><option value="INDIVIDUAL">Individual</option><option value="PROFESSIONAL">Professional</option><option value="ENTREPRENEUR">Entrepreneur / Business</option><option value="ORGANIZATION">Organization</option></select><input id="reg-email" class="input" type="email" placeholder="Email" autocomplete="email"><input id="reg-password" class="input" type="password" placeholder="Password minimal 8 karakter" autocomplete="new-password"><button class="primary" onclick="submitSelfRegister()">Daftar & Masuk</button><div id="reg-result" style="margin-top:12px"></div></div>'}
async function submitSelfRegister(){const out=document.getElementById('reg-result');const name=document.getElementById('reg-name').value.trim();const email=document.getElementById('reg-email').value.trim();const password=document.getElementById('reg-password').value;if(!name||!email||password.length<8){out.textContent='Nama, email, dan password minimal 8 karakter diperlukan.';return}out.textContent='Membuat identitas...';try{const r=await fetch('/api/public/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,email,password,context:(document.getElementById('reg-context')||{}).value||'CANDIDATE'})});const d=await r.json();if(!r.ok){out.textContent=d.error==='account_exists'?'Akun sudah ada. Silakan masuk.':'Registrasi gagal: '+(d.error||'unknown_error');return}try{sessionStorage.setItem('vcmc_token',d.token)}catch(_){}const l=document.getElementById('login'),a=document.getElementById('app'),n=document.getElementById('nav');if(l)l.classList.add('hidden');if(a)a.classList.remove('hidden');if(n)n.classList.remove('hidden');if(window.boot)return window.boot();}catch(e){out.textContent='Koneksi gagal.'}}
function showPublicLane(kind){const box=document.getElementById('public-lane');const invited=kind==='invited';box.innerHTML='<div class="card" style="margin:0"><div class="sectionhead"><h3>'+(invited?'Invited / Existing Partner':'Public / Independent')+'</h3><button type="button" class="back" data-public-close>Tutup</button></div><p class="muted" style="margin-bottom:10px">Registration ≠ Approval · Login ≠ Authority · Email ≠ Partner</p><input id="pub-name" class="input" placeholder="Nama / Name"><input id="pub-org" class="input" placeholder="Organisasi / Organization"><input id="pub-country" class="input" placeholder="Negara / Country"><select id="pub-language" class="input"><option value="id">Bahasa Indonesia</option><option value="en">English</option><option value="ar">العربية</option><option value="es">Español</option><option value="fr">Français</option></select><select id="pub-contact-type" class="input"><option value="phone">Phone / WhatsApp</option><option value="email">Email</option></select><input id="pub-contact" class="input" placeholder="Phone / WhatsApp / Email"><input id="pub-message" class="input" placeholder="Tujuan / opportunity / kebutuhan"><input id="pub-invite" class="input" placeholder="Invitation code (jika ada)" '+(invited?'':'style="display:none"')+'><button class="primary" onclick="submitPublicRequest(\''+kind+'\')">Ajukan Akses</button><div id="pub-result" style="margin-top:12px"></div></div>'}
async function trackPublicRequest(){const id=(document.getElementById('pub-track')||{}).value?.trim();const out=document.getElementById('pub-track-result');if(!id||!out)return;out.textContent='Memeriksa status...';try{const r=await fetch('/api/public/access-request?id='+encodeURIComponent(id));const d=await r.json();if(!r.ok){out.textContent='Request tidak ditemukan.';return}out.innerHTML='<div class="feeditem"><b>'+esc(d.request.status)+'</b><br><span class="muted">'+esc(d.request.name)+' · '+esc(d.request.request_type)+' · '+esc(d.request.updated_at)+'</span></div>'}catch(e){out.textContent='Koneksi gagal.'}}
async function submitPublicRequest(kind){const out=document.getElementById('pub-result');const name=document.getElementById('pub-name').value.trim();const contact=document.getElementById('pub-contact').value.trim();if(!name||!contact){out.textContent='Nama dan satu kontak diperlukan.';return}out.textContent='Mencatat permintaan...';try{const r=await fetch('/api/public/access-requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_type:kind,name,organization:document.getElementById('pub-org').value.trim(),country:document.getElementById('pub-country').value.trim(),language:document.getElementById('pub-language').value,contact_type:document.getElementById('pub-contact-type').value,contact_value:contact,message:document.getElementById('pub-message').value.trim(),invitation_code:document.getElementById('pub-invite').value.trim()})});const d=await r.json();if(!r.ok){out.textContent='Permintaan belum dapat dicatat: '+(d.error||'unknown_error');return}out.innerHTML='<div class="feeditem"><b>REQUESTED</b><br>ID: '+esc(d.id)+'<br><span class="muted">Permintaan tercatat. Approval diperlukan sebelum akun dapat dibuat.</span></div><div class="card" style="margin-top:10px"><b>Lacak status permintaan</b><input id="pub-track" class="input" value="'+esc(d.id)+'" placeholder="Request ID"><button type="button" class="action" onclick="trackPublicRequest()">Cek Status</button><div id="pub-track-result" style="margin-top:10px"></div></div><div class="card" style="margin-top:10px"><b>Aktivasi akun</b><p class="muted" style="margin:6px 0">Aktivasi hanya tersedia setelah VCMC memberi status Candidate/Partner dan memberikan kode aktivasi.</p><input id="act-request" class="input" value="'+esc(d.id)+'" placeholder="Request ID"><input id="act-code" class="input" placeholder="Activation code"><input id="act-password" class="input" type="password" placeholder="Password baru (minimal 8 karakter)"><button type="button" class="primary" onclick="activateAccount()">Aktifkan & Masuk</button><div id="act-result" style="margin-top:10px"></div></div>'}catch(e){out.textContent='Koneksi gagal.'}}
document.addEventListener('click',function(e){if(e.target.closest&&e.target.closest('[data-public-close]')){var b=document.getElementById('public-lane');if(b)b.innerHTML=''}},true);
async function activateAccount(){const out=document.getElementById('act-result');try{const r=await fetch('/api/public/activate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:document.getElementById('act-request').value.trim(),activation_code:document.getElementById('act-code').value.trim(),password:document.getElementById('act-password').value})});const d=await r.json();if(!r.ok){out.textContent=d.error||'Aktivasi gagal.';return}try{sessionStorage.setItem('vcmc_token',d.token)}catch(_){};token=d.token;out.textContent='Akun aktif. Membuka VCMC-VP...';await boot()}catch(e){out.textContent='Koneksi gagal.'}}
let token=null;try{token=sessionStorage.getItem('vcmc_token')}catch(e){token=null}let me=null;let home=null;
async function api(path,opt={}){opt.headers=Object.assign({'Content-Type':'application/json'},opt.headers||{});if(token)opt.headers.Authorization='Bearer '+token;opt.credentials='same-origin';const r=await fetch(path,opt);if(r.status===401){sessionStorage.removeItem('vcmc_token');showLogin();throw new Error('unauthorized')}return r.json()}
function showLogin(){document.getElementById('login').classList.remove('hidden');document.getElementById('app').classList.add('hidden');document.getElementById('nav').classList.add('hidden')}
function showApp(){document.getElementById('login').classList.add('hidden');document.getElementById('app').classList.remove('hidden');document.getElementById('nav').classList.remove('hidden')}
function active(tab){document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('active',x.dataset.tab===tab))}
function esc(x){return String(x??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
async function boot(){try{me=await api('/api/me');home=await api('/api/home');showApp();await go('home')}catch(e){sessionStorage.removeItem('vcmc_token');token=null;showLogin();const msg=document.getElementById('msg');if(msg)msg.textContent='Session gagal dibuka. Silakan masuk kembali.';}}
async function go(tab){showApp();active(tab);document.getElementById('title').textContent=({home:'Home',network:'Global Network',explore:'Explore',evidence:'Evidence',profile:'Profile'})[tab]||'VCMC-VP';if(tab==='home')return renderHome();if(tab==='network')return renderNetwork();if(tab==='explore')return renderExplore();if(tab==='evidence')return renderEvidence();if(tab==='profile')return renderProfile()}
function renderHome(){const m=home.metrics;const architecture='<section class="sectionhead"><h3>VCMC Architecture</h3><span>Foundation → Operation → Proof → Benefit</span></section><div class="rooms"><button class="room" type="button" onclick="room('architecture','Architecture')"><b>Architecture</b><br><small>TAQDA · governance · evidence · reconciliation · global network · development</small></button><button class="room" type="button" onclick="go('network')"><b>Global Network</b><br><small>Identify · Screen · Classify · Route · Interact · Evidence · Reconcile</small></button><button class="room" type="button" onclick="room('partners','Partners & Candidates')"><b>Partners & Candidates</b><br><small>Public → Screening → Candidate → Partner</small></button><button class="room" type="button" onclick="room('pilots','Pilots')"><b>Pilots</b><br><small>Candidate ≠ Pilot · readiness separated from proof</small></button><button class="room" type="button" onclick="room('projects','Programs & Projects')"><b>Programs & Projects</b><br><small>Need → Program → Project → Pilot → Result</small></button><button class="room" type="button" onclick="room('development','Development Direction')"><b>Development Direction</b><br><small>Direction · priority · authorization · learning</small></button></div>';const operations='<section class="sectionhead"><h3>Operational Rooms</h3><span>'+home.rooms.length+' connected</span></section><div class="rooms">'+home.rooms.map(r=>'<div class="room" onclick="room(\''+r.id+'\',\''+esc(r.name)+'\')"><b>'+esc(r.name)+'</b><br><small>'+esc(r.status)+'</small></div>').join('')+'</div>';document.getElementById('content').innerHTML='<section class="card hero"><div class="eyebrow">VCMC-VP · GLOBAL OPERATIONAL PLATFORM</div><h2 style="margin:5px 0 8px">Pintu masuk ke arsitektur VCMC</h2><p class="muted">VCMC-VP bukan lemari pribadi. Ini adalah mesin operasional untuk jaringan global: identity → status → authority → access → action → evidence → reconciliation → real benefit.</p><div class="identity" style="margin-top:14px"><div><div class="muted">Current context</div><b>'+esc(me.context||'PUBLIC')+'</b></div><div style="text-align:right"><div class="muted">Status / role</div><b>'+esc(me.role||'PUBLIC')+'</b></div></div><div class="actions" style="margin-top:14px"><button class="action" onclick="go(\'network\')"><b>Global Network</b><br><span class="muted">Jaringan dan interaksi lintas yurisdiksi</span></button><button class="action" onclick="room(\'architecture\',\'Architecture\')"><b>Open Architecture</b><br><span class="muted">Lihat fondasi dan batas kewenangan</span></button><button class="action" onclick="room(\'partners\',\'Partners & Candidates\')"><b>Public → Partner</b><br><span class="muted">Jalur publik tanpa menganggap registrasi sebagai approval</span></button><button class="action" onclick="go(\'evidence\')"><b>Evidence & Proof</b><br><span class="muted">Claim ≠ Evidence · Recorded ≠ Done ≠ Proven</span></button></div></section>'+architecture+'<section class="sectionhead"><h3>System & Control</h3><span>Live from API</span></section><div class="grid"><div class="tile"><b>Cases</b>'+m.cases+'</div><div class="tile"><b>Evidence</b>'+m.evidence+'</div><div class="tile"><b>Audit</b>'+m.audit+'</div><div class="tile"><b>Reconciliation</b>'+m.reconciliations+'</div></div><section class="sectionhead"><h3>Control Boundary</h3><span>Honesty layer</span></section><div class="feed"><div class="feeditem attention"><b>Proof</b><br><span class="muted">READY ≠ PROVEN · evidence remains required.</span></div><div class="feeditem"><b>Payment</b><br><span class="muted">REAL_MONEY remains '+(home.system.real_money_enabled?'enabled':'simulation only')+'; execution proof is separate.</span></div><div class="feeditem"><b>Authority</b><br><span class="muted">Identity ≠ Status ≠ Authority ≠ Access. Public registration never grants automatic approval or partner authority.</span></div></div>'+operations+'<section class="sectionhead"><h3>Current Identity</h3><span>'+esc(me.role)+'</span></section><div class="card detail"><b>'+esc(me.name||me.email)+'</b><p class="muted">'+esc(me.email)+' · '+esc(me.role)+' · session active</p><p class="muted" style="margin-top:8px">Personal settings are one part of the system, not the purpose of VCMC-VP.</p></div>'}async function renderNetwork(){const d=await api('/api/network');document.getElementById('content').innerHTML='<div class="card hero"><div class="eyebrow">CONNECTED NETWORK</div><h2>Global Network</h2><p class="muted">Identify → Screen → Classify → Route → Interact → Evidence → Reconcile</p></div><div class="grid"><div class="tile"><b>Entities</b>'+d.entities+'</div><div class="tile"><b>Relationships</b>'+d.relationships+'</div><div class="tile"><b>Active sessions</b>'+d.active_sessions+'</div><div class="tile"><b>Screening</b>Context controlled</div></div><section class="sectionhead"><h3>Recent Activity</h3></section><div class="feed">'+(d.activity.length?d.activity.map(x=>'<div class="feeditem"><b>'+esc(x.action)+'</b><br><span class="muted">'+esc(x.entity)+' · '+esc(x.at)+'</span></div>').join(''):'<div class="empty">Belum ada aktivitas jaringan.</div>')+'</div>'}
function renderExplore(){document.getElementById('content').innerHTML='<div class="card hero"><div class="eyebrow">ALL-IN-ONE</div><h2>Explore VCMC-VP</h2><p class="muted">Satu rumah, banyak kamar. Setiap kamar punya fungsi, status, authority, evidence dan reconciliation.</p></div><div class="rooms">'+home.rooms.map(r=>'<div class="room" onclick="room(\''+r.id+'\',\''+esc(r.name)+'\')"><b>'+esc(r.name)+'</b><br><small>'+esc(r.status)+'</small></div>').join('')+'</div>'}
async function renderEvidence(){const d=await api('/api/evidence');document.getElementById('content').innerHTML='<div class="card hero"><div class="eyebrow">PROOF LAYER</div><h2>Evidence Center</h2><p class="muted">CLAIM → RECORDED → EVIDENCE SUBMITTED → VERIFIED → RECONCILED → PROVEN</p></div><div class="grid"><div class="tile"><b>Evidence records</b>'+d.count+'</div><div class="tile"><b>Verified</b>'+d.verified+'</div><div class="tile"><b>Unverified</b>'+d.unverified+'</div><div class="tile"><b>Rule</b>Evidence required</div></div><div class="card"><h3>Submit Evidence</h3><input id="ev-case" class="input" placeholder="Case ID"><input id="ev-kind" class="input" placeholder="Evidence kind" value="CASE_EVIDENCE"><input id="ev-payload" class="input" placeholder="Evidence payload / reference"><button class="primary" onclick="submitEvidence()">Catat Evidence</button><div id="ev-result" style="margin-top:12px"></div></div><div class="card"><h3>Evidence Registry</h3><div class="feed">'+(d.items.length?d.items.map(x=>'<div class="feeditem"><b>'+esc(x.kind)+'</b><br><span class="muted">'+esc(x.case_id)+' · '+esc(x.sha256)+'</span></div>').join(''):'<div class="empty">Belum ada evidence tercatat.</div>')+'</div></div>'}
async function changePassword(){const m=document.getElementById('pw-msg'),cur=document.getElementById('pw-current'),np=document.getElementById('pw-new');if(!cur||!np)return;if(np.value.length<8){m.textContent='Password baru minimal 8 karakter.';return}if(cur.value===np.value){m.textContent='Password baru harus berbeda.';return}api('/api/password/change',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:cur.value,new_password:np.value})}).then(async r=>{const d=await r.json();if(!r.ok){m.textContent=d.error==='current_password_incorrect'?'Password saat ini salah.':'Gagal mengubah password: '+(d.error||'unknown_error');return}m.textContent='Password berhasil diubah.';cur.value='';np.value=''}).catch(()=>m.textContent='Koneksi gagal.')}
function updateAccount(){const m=document.getElementById('acct-msg'),cur=document.getElementById('acct-current'),name=document.getElementById('acct-name'),email=document.getElementById('acct-email');api('/api/account/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:cur.value,name:name.value,email:email.value})}).then(async r=>{const d=await r.json();if(!r.ok){m.textContent=d.error==='current_password_incorrect'?'Password saat ini salah.':d.error==='email_in_use'?'Email sudah digunakan akun lain.':'Gagal menyimpan: '+(d.error||'unknown_error');return}me.name=d.name;me.email=d.email;m.textContent='Identitas akun tersimpan.';cur.value=''}).catch(()=>m.textContent='Koneksi gagal.')}
function revokeOtherSessions(){const m=document.getElementById('session-msg');api('/api/sessions/revoke-other',{method:'POST'}).then(async r=>{const d=await r.json();m.textContent=r.ok?'Sesi lain dicabut: '+d.revoked_sessions:'Gagal mencabut sesi lain.'}).catch(()=>m.textContent='Koneksi gagal.')}
function renderProfile(){document.getElementById('content').innerHTML='<div class="card hero"><div class="eyebrow">MY ACCOUNT</div><h2>'+esc(me.name||me.email)+'</h2><p class="muted">'+esc(me.email)+'</p></div><div class="card detail"><div class="eyebrow">IDENTITY</div><b>Nama</b><p>'+esc(me.name||'—')+'</p><b>Email</b><p>'+esc(me.email)+'</p><b>Login ID</b><p>'+esc(me.login_id||'—')+'</p><b>Role</b><p>'+esc(me.role||'—')+'</p><b>Authority</b><p>'+esc(me.role==='SOVEREIGN'?'SOVEREIGN':'Context controlled')+'</p><p class="muted">Role, status, authority, dan aturan VCMC tidak dapat diubah dari pengaturan pribadi.</p></div><div class="card"><div class="eyebrow">ACCOUNT</div><h3>Identitas & Email</h3><input id="acct-name" class="input" type="text" placeholder="Nama" value="'+esc(me.name||'')+'"><input id="acct-email" class="input" type="email" placeholder="Email" value="'+esc(me.email||'')+'"><input id="acct-current" class="input" type="password" placeholder="Password saat ini" autocomplete="current-password"><button class="primary" type="button" onclick="updateAccount()">Simpan Identitas & Email</button><div id="acct-msg" class="muted"></div></div><div class="card"><div class="eyebrow">SECURITY</div><h3>Ubah Password</h3><input id="pw-current" class="input" type="password" placeholder="Password saat ini" autocomplete="current-password"><input id="pw-new" class="input" type="password" placeholder="Password baru" autocomplete="new-password"><button class="primary" type="button" onclick="changePassword()">Simpan Password Baru</button><div id="pw-msg" class="muted"></div></div><div class="card"><div class="eyebrow">SESSIONS</div><h3>Keamanan Sesi</h3><p class="muted">Cabut sesi lain tanpa mengakhiri sesi yang sedang digunakan.</p><button class="action" type="button" onclick="revokeOtherSessions()">Cabut Sesi Lain</button><div id="session-msg" class="muted"></div></div>'}
function architectureSection(key){
  const sections={
    foundation:['Identity / Foundation','TAUHID AL-QUR\'AN DIGITAL (TAQDA)','TAQDA → VCMC → Real Development → Real Benefit → Global Scale','Vision & Foundation · Kejujuran Mutlak · 4 Pillars · Identity → Role → Authority → Permission','VCMC adalah governance, allocation, control, dan reconciliation layer; bukan bank, PJP, fund holder, payment executor, investor, operator, atau middleman.'],
    governance:['Governance','Separation of Authority','MENENTUKAN ≠ MENGHITUNG ≠ MEMEGANG DANA ≠ MEMBAYAR ≠ MENERIMA','Candidate ≠ Pilot · READY ≠ PROVEN · UNKNOWN ≠ FAILED','Authorization dan accountability harus memiliki konteks, batas, dan pihak yang bertanggung jawab.'],
    evidence:['Evidence','CLAIM → RECORDED → EVIDENCE SUBMITTED → VERIFIED → RECONCILED → PROVEN','Evidence ID · hash · source · time · responsible party','Audit trail harus dapat ditelusuri.','Claim, AI, automation, dan status sistem tidak menggantikan evidence.'],
    reconciliation:['Reconciliation','Amount → Destination → Purpose → Responsible Party → Evidence → Result → Reconciliation','Planned vs Actual','Expected / Executed / Received / Ledger','Exception atau Hold dicatat dan dikendalikan; reconciliation adalah control, bukan sekadar laporan.'],
    network:['Global Network','Identify → Screen → Classify → Route → Authorize → Interact → Evidence → Reconcile','Global & Cross-Border · Indonesia sebagai origin, cakupan global/lintas yurisdiksi','Partner · Candidate · Pilot · Project · Program · Provider','Automatic screening ≠ automatic authority · detection ≠ proof · classification ≠ ownership.'],
    development:['Development','Need → Direction → Priority → Program → Project → Pilot → Result → Real Benefit','Development Direction · Capital & Development','Distribution: Gross → 2.5% Zakat → 97.5% remainder → 40/40/20','Observe → Detect → Measure → Evidence → Analyze → Propose → Review → Test → Authorize → Release → Monitor → Reconcile → Learn.']
  };
  const s=sections[key]||sections.foundation;
  document.getElementById('title').textContent='Architecture V1';
  document.getElementById('content').innerHTML='<div class="card hero"><button class="back" onclick="renderArchitecture()">← Kembali ke Architecture</button><div class="eyebrow" style="margin-top:18px">ARCHITECTURE V1 · INTERIOR</div><h2 style="margin:5px 0 8px">'+s[0]+'</h2><p class="muted">VCMC Architecture · detail layer</p></div><div class="card detail">'+s.slice(1).map(x=>'<div class="feeditem" style="margin:10px 0"><span class="muted">'+x+'</span></div>').join('')+'</div><div class="card"><button class="action" style="width:100%" onclick="go(\'home\')">Kembali ke Home</button></div>';
}
function renderArchitecture(){
  document.getElementById('title').textContent='Architecture V1';
  document.getElementById('content').innerHTML='<div class="card hero"><div class="eyebrow">ARCHITECTURE V1</div><h2 style="margin:5px 0 8px">VCMC Architecture</h2><p class="muted">Struktur awal VCMC-VP — identitas, governance, evidence, reconciliation, global network, dan development.</p></div><div class="rooms"><div class="room" onclick="architectureSection(\'foundation\')"><b>Identity / Foundation</b><br><small>Identity, TAUHID AL-QUR\'AN DIGITAL (TAQDA), vision & principles</small></div><div class="room" onclick="architectureSection(\'governance\')"><b>Governance</b><br><small>Authority, boundaries & accountability</small></div><div class="room" onclick="architectureSection(\'evidence\')"><b>Evidence</b><br><small>Proof, verification & audit trail</small></div><div class="room" onclick="architectureSection(\'reconciliation\')"><b>Reconciliation</b><br><small>Amount, destination, result & control</small></div><div class="room" onclick="architectureSection(\'network\')"><b>Global Network</b><br><small>Global, cross-border & interaction</small></div><div class="room" onclick="architectureSection(\'development\')"><b>Development</b><br><small>Need → Direction → Result → Real Benefit</small></div></div>';
}
async function room(id,name){
 if(id==='architecture')return renderArchitecture();
 if(id==='network')return renderNetwork();
 if(id==='evidence')return renderEvidence();
 const title=esc(name);
 const shell=(body)=>{document.getElementById('title').textContent=name;document.getElementById('content').innerHTML='<div class="card hero"><button class="back" onclick="go(\'home\')">← Kembali ke Home</button><div class="eyebrow" style="margin-top:18px">VCMC ROOM · FUNCTIONAL</div><h2 style="margin:5px 0 8px">'+title+'</h2><p class="muted">Room '+esc(id)+' · fungsi teruji melalui API VCMC-VP.</p></div>'+body};
 if(id==='partners'){
   const d=await api('/api/partners'); const rq=await api('/api/public/access-requests');
   shell('<div class="card"><h3>Public Access Requests</h3><p class="muted">Public → Screening → Candidate → Partner. Status does not itself grant authority.</p><div class="feed">'+(rq.items.length?rq.items.map(x=>'<div class="feeditem"><b>'+esc(x.name)+'</b><br><span class="muted">'+esc(x.id)+' · '+esc(x.request_type)+' · '+esc(x.status)+'</span><div class="actions" style="margin-top:8px"><button class="action" onclick="reviewAccess(\''+esc(x.id)+'\',\'SCREENING\')">Screening</button><button class="action" onclick="reviewAccess(\''+esc(x.id)+'\',\'CANDIDATE\')">Candidate</button><button class="action" onclick="reviewAccess(\''+esc(x.id)+'\',\'PARTNER\')">Partner</button><button class="action" onclick="reviewAccess(\''+esc(x.id)+'\',\'HOLD\')">Hold</button></div></div>').join(''):'<div class="empty">Belum ada public request.</div>')+'</div></div><div class="card"><h3>Partner & Candidate Registry</h3><p class="muted" style="margin:6px 0 12px">Mencatat kandidat/mitra tanpa menganggap READY sebagai PROVEN.</p><input id="partner-name" class="input" placeholder="Nama entitas"><input id="partner-contact" class="input" placeholder="Kontak / kanal resmi (opsional)"><div class="grid"><select id="partner-kind" class="input"><option>CANDIDATE</option><option>PARTNER</option></select><select id="partner-status" class="input"><option>CANDIDATE</option><option>SCREENING</option><option>READY</option><option>HOLD</option><option>UNKNOWN</option></select></div><button class="primary" onclick="registerPartner()">Catat Entitas</button><div id="partner-result" style="margin-top:12px"></div></div><div class="card"><h3>Registry</h3><div id="partner-list">'+(d.items.length?d.items.map(x=>'<div class="feeditem" style="margin:10px 0"><b>'+esc(x.name)+'</b><br><span class="muted">'+esc(x.kind)+' · '+esc(x.status)+(x.contact?' · '+esc(x.contact):'')+'</span></div>').join(''):'<div class="empty">Belum ada entitas tercatat.</div>')+'</div></div>');return;
 }
 if(id==='pilots'){
   const d=await api('/api/pilots');
   shell('<div class="card"><h3>Pilot Registry</h3><p class="muted">Pilot berdiri terpisah dari kandidat/mitra. Candidate != Pilot.</p><input id="pilot-name" class="input" placeholder="Nama pilot"><input id="pilot-partner" class="input" placeholder="Partner ID (opsional)"><input id="pilot-objective" class="input" placeholder="Tujuan pilot"><select id="pilot-status" class="input"><option>PILOT_CANDIDATE</option><option>SCREENING</option><option>READY</option><option>ACTIVE</option><option>HOLD</option><option>UNKNOWN</option></select><button class="primary" onclick="registerPilot()">Catat Pilot</button><div id="pilot-result"></div></div><div class="card"><h3>Registri Pilot</h3><div id="pilot-list">'+(d.items.length?d.items.map(x=>'<div class="feeditem"><b>'+esc(x.name)+'</b><br><span class="muted">'+esc(x.status)+(x.partner_id?' · '+esc(x.partner_id):'')+'</span><br>'+esc(x.objective||'')+'</div>').join(''):'<div class="empty">Belum ada pilot tercatat.</div>')+'</div></div>');return;
 }
 if(id==='projects'){
   const d=await api('/api/projects');
   shell('<div class="card"><h3>Programs & Projects Registry</h3><p class="muted">Menghubungkan program/proyek dengan pilot tanpa mengubah authority.</p><input id="project-name" class="input" placeholder="Nama program/proyek"><input id="project-pilot" class="input" placeholder="Pilot ID (opsional)"><div class="grid"><select id="project-kind" class="input"><option>PROJECT</option><option>PROGRAM</option></select><select id="project-status" class="input"><option>DRAFT</option><option>PLANNING</option><option>ACTIVE</option><option>HOLD</option><option>COMPLETED</option><option>UNKNOWN</option></select></div><button class="primary" onclick="registerProject()">Catat Program/Proyek</button><div id="project-result"></div></div><div class="card"><h3>Registri</h3><div id="project-list">'+(d.items.length?d.items.map(x=>'<div class="feeditem"><b>'+esc(x.name)+'</b><br><span class="muted">'+esc(x.kind)+' · '+esc(x.status)+(x.pilot_id?' · '+esc(x.pilot_id):'')+'</span></div>').join(''):'<div class="empty">Belum ada program/proyek tercatat.</div>')+'</div></div>');return;
 }
 if(id==='development'){
   const d=await api('/api/directions');
   shell('<div class="card"><h3>Development Direction</h3><p class="muted">Need → Direction → Priority → Program → Project → Pilot → Result.</p><input id="direction-name" class="input" placeholder="Arah pengembangan"><div class="grid"><select id="direction-priority" class="input"><option>NORMAL</option><option>LOW</option><option>HIGH</option><option>CRITICAL</option></select><select id="direction-status" class="input"><option>PROPOSED</option><option>REVIEW</option><option>AUTHORIZED</option><option>HOLD</option><option>UNKNOWN</option></select></div><button class="primary" onclick="registerDirection()">Catat Arah</button><div id="direction-result"></div></div><div class="card"><h3>Registri Arah</h3><div id="direction-list">'+(d.items.length?d.items.map(x=>'<div class="feeditem"><b>'+esc(x.name)+'</b><br><span class="muted">'+esc(x.priority)+' · '+esc(x.status)+'</span></div>').join(''):'<div class="empty">Belum ada arah tercatat.</div>')+'</div></div>');return;
 }
 if(id==='capital'){
   const d=await api('/api/capital-plans');
   shell('<div class="card"><h3>Capital & Development</h3><p class="muted">Struktur rencana modal/pengembangan; VCMC tidak memegang dana.</p><input id="capital-name" class="input" placeholder="Nama rencana"><input id="capital-purpose" class="input" placeholder="Tujuan"><div class="grid"><input id="capital-amount" class="input" type="number" min="0" placeholder="Nilai rencana"><select id="capital-status" class="input"><option>PLANNED</option><option>REVIEW</option><option>AUTHORIZED</option><option>HOLD</option><option>UNKNOWN</option></select></div><button class="primary" onclick="registerCapital()">Catat Rencana</button><div id="capital-result"></div></div><div class="card"><h3>Registri Rencana</h3><div id="capital-list">'+(d.items.length?d.items.map(x=>'<div class="feeditem"><b>'+esc(x.name)+'</b><br><span class="muted">'+esc(x.status)+' · '+x.amount+'</span><br>'+esc(x.purpose)+'</div>').join(''):'<div class="empty">Belum ada rencana tercatat.</div>')+'</div></div>');return;
 }
 if(id==='distribution'){shell('<div class="card"><h3>Distribution Calculator</h3><p class="muted" style="margin:6px 0 12px">Hitung tanpa eksekusi uang nyata.</p><input id="dist-gross" class="input" type="number" min="0" placeholder="Gross amount"><button class="primary" onclick="runDistribution()">Hitung</button><div id="dist-result" style="margin-top:12px"></div></div>');return;}
 if(id==='reconciliation'){const d=await api('/api/reconciliation');shell('<div class="card"><h3>Reconciliation Check</h3><p class="muted" style="margin:6px 0 12px">Bandingkan expected, executed, received, dan ledger.</p><input id="rec-case" class="input" placeholder="Case ID"><div class="grid"><input id="rec-expected" class="input" type="number" placeholder="Expected"><input id="rec-executed" class="input" type="number" placeholder="Executed"><input id="rec-received" class="input" type="number" placeholder="Received"><input id="rec-ledger" class="input" type="number" placeholder="Ledger"></div><button class="primary" onclick="runReconciliation()">Periksa Rekonsiliasi</button><div id="rec-result" style="margin-top:12px"></div></div><div class="card"><h3>Reconciliation Registry</h3><div class="feed">'+(d.items.length?d.items.map(x=>'<div class="feeditem"><b>'+esc(x.status)+'</b><br><span class="muted">'+esc(x.case_id)+' · Expected '+x.expected+' · Executed '+x.executed+' · Received '+x.received+' · Ledger '+x.ledger+'</span></div>').join(''):'<div class="empty">Belum ada rekonsiliasi tercatat.</div>')+'</div></div>');return;}
 if(id==='payment'){shell('<div class="card"><h3>Payment / Providers</h3><p class="muted" style="margin:6px 0 12px">Mode saat ini hanya simulasi; tidak mengeksekusi uang nyata.</p><input id="pay-case" class="input" placeholder="Case ID"><button class="primary" onclick="runPaymentSimulation()">Buat Instruction Simulasi</button><div id="pay-result" style="margin-top:12px"></div></div>');return;}
 if(id==='security'){const r=await api('/api/system/readiness');shell('<div class="card detail"><b>Authentication</b><p>Bearer session · /api/me</p><br><b>Security headers</b><p>X-Content-Type-Options · X-Frame-Options · Referrer-Policy · Cache-Control</p><br><b>Real money</b><p>'+esc(r.real_money_enabled?'ENABLED':'DISABLED / SIMULATION')+'</p><br><b>PJP execution verified</b><p>'+esc(r.real_pjp_execution_verified?'YES':'NO')+'</p></div>');return;}
 if(id==='system'){const [r,m,b]=await Promise.all([api('/api/system/readiness'),api('/api/metrics'),api('/api/backups')]);shell('<div class="grid"><div class="tile"><b>Health</b>API reachable</div><div class="tile"><b>Cases</b>'+m.cases+'</div><div class="tile"><b>Audit events</b>'+m.audit_events+'</div><div class="tile"><b>Readiness</b>'+esc(r.ready?'READY (simulation boundary)':'HOLD')+'</div></div><div class="card"><h3>Backup</h3><p class="muted">Database backup is created with SHA-256 evidence.</p><button class="primary" onclick="createBackup()">Buat Backup</button><div id="backup-result" style="margin-top:12px"></div></div><div class="card"><h3>Backup Registry</h3><div class="feed">'+(b.items.length?b.items.map(x=>'<div class="feeditem"><b>'+esc(x.created_at)+'</b><br><span class="muted">'+esc(x.sha256)+'</span></div>').join(''):'<div class="empty">Belum ada backup tercatat.</div>')+'</div></div><div class="card detail"><b>Control principle</b><p class="muted">Recorded ≠ Done ≠ Proven.</p></div>');return;}
 const status=(home.rooms.find(x=>x.id===id)||{}).status||'registered';shell('<div class="card detail"><b>Status</b><p>'+esc(status)+'</p><br><b>Boundary</b><p class="muted">Room terdaftar dan identitasnya tersedia. Fungsi operasional belum dibuka pada tahap ini; tidak dianggap proven.</p></div>');
}
async function reviewAccess(id,status){try{const d=await api('/api/public/access-requests/review',{method:'POST',body:JSON.stringify({id:id,status:status})});let msg='Status diperbarui: '+d.status;if(d.activation_code)msg+='\n\nKode aktivasi akun: '+d.activation_code+'\nBerlaku 7 hari. Berikan kode ini kepada pemilik email yang disetujui.';alert(msg);await room('partners','Partners & Candidates')}catch(e){alert('Review gagal: '+(e.message||'unknown_error'))}}
async function registerPartner(){const out=document.getElementById('partner-result');try{const d=await api('/api/partners',{method:'POST',body:JSON.stringify({name:document.getElementById('partner-name').value,contact:document.getElementById('partner-contact').value,kind:document.getElementById('partner-kind').value,status:document.getElementById('partner-status').value})});out.textContent='Tercatat: '+d.id+' · '+d.status;const list=document.getElementById('partner-list');if(list.querySelector('.empty'))list.innerHTML='';list.insertAdjacentHTML('afterbegin','<div class="feeditem" style="margin:10px 0"><b>'+esc(d.name)+'</b><br><span class="muted">'+esc(d.kind)+' · '+esc(d.status)+(d.contact?' · '+esc(d.contact):'')+'</span></div>');document.getElementById('partner-name').value='';document.getElementById('partner-contact').value=''}catch(e){out.textContent='Pencatatan gagal: '+e.message}}
async function registerPilot(){const out=document.getElementById('pilot-result');try{const d=await api('/api/pilots',{method:'POST',body:JSON.stringify({name:document.getElementById('pilot-name').value,partner_id:document.getElementById('pilot-partner').value,objective:document.getElementById('pilot-objective').value,status:document.getElementById('pilot-status').value})});out.textContent='Tercatat: '+d.id;await room('pilots','Pilots')}catch(e){out.textContent='Pencatatan gagal: '+e.message}}
async function registerProject(){const out=document.getElementById('project-result');try{const d=await api('/api/projects',{method:'POST',body:JSON.stringify({name:document.getElementById('project-name').value,pilot_id:document.getElementById('project-pilot').value,kind:document.getElementById('project-kind').value,status:document.getElementById('project-status').value})});out.textContent='Tercatat: '+d.id;await room('projects','Programs & Projects')}catch(e){out.textContent='Pencatatan gagal: '+e.message}}
async function registerDirection(){const out=document.getElementById('direction-result');try{const d=await api('/api/directions',{method:'POST',body:JSON.stringify({name:document.getElementById('direction-name').value,priority:document.getElementById('direction-priority').value,status:document.getElementById('direction-status').value})});out.textContent='Tercatat: '+d.id;await room('development','Development Direction')}catch(e){out.textContent='Pencatatan gagal: '+e.message}}
async function registerCapital(){const out=document.getElementById('capital-result');try{const d=await api('/api/capital-plans',{method:'POST',body:JSON.stringify({name:document.getElementById('capital-name').value,purpose:document.getElementById('capital-purpose').value,amount:document.getElementById('capital-amount').value,status:document.getElementById('capital-status').value})});out.textContent='Tercatat: '+d.id;await room('capital','Capital & Development')}catch(e){out.textContent='Pencatatan gagal: '+e.message}}
async function runDistribution(){const out=document.getElementById('dist-result');try{const g=document.getElementById('dist-gross').value;if(!g){out.textContent='Masukkan gross amount.';return}const d=await api('/api/calculate',{method:'POST',body:JSON.stringify({gross:g})});out.innerHTML='<div class="feeditem"><b>Gross</b> '+d.gross+'<br>Zakat: '+d.zakat+'<br>Mitra/Pelaksana: '+d.mitra+'<br>Pusat VCMC: '+d.pusat+'<br>Amal & Kemanusiaan: '+d.amal+'<br>Pusat → IP/Hak Cipta: '+d.ip+'<br>Pusat → Dana Pengembangan: '+d.development+'<br>Pusat → Cadangan: '+d.reserve+'<br><span class="muted">Formula '+esc(d.formula_version)+'</span></div>'}catch(e){out.textContent='Perhitungan gagal.'}}
async function submitEvidence(){const out=document.getElementById('ev-result');try{const d=await api('/api/evidence',{method:'POST',body:JSON.stringify({case_id:document.getElementById('ev-case').value,kind:document.getElementById('ev-kind').value,payload:{reference:document.getElementById('ev-payload').value}})});out.textContent='Tercatat: '+d.sha256;await renderEvidence()}catch(e){out.textContent='Evidence gagal: '+e.message}}
async function createBackup(){const out=document.getElementById('backup-result');try{const d=await api('/api/backups/create',{method:'POST'});out.textContent='Backup tercatat: '+d.sha256;await room('system','System & Operations')}catch(e){out.textContent='Backup gagal: '+e.message}}
async function runReconciliation(){const out=document.getElementById('rec-result');try{const d=await api('/api/reconciliation',{method:'POST',body:JSON.stringify({case_id:document.getElementById('rec-case').value,expected:document.getElementById('rec-expected').value,executed:document.getElementById('rec-executed').value,received:document.getElementById('rec-received').value,ledger:document.getElementById('rec-ledger').value})});out.innerHTML='<div class="feeditem"><b>'+esc(d.status)+'</b><br>Expected '+d.expected+' · Executed '+d.executed+' · Received '+d.received+' · Ledger '+d.ledger+'</div>'}catch(e){out.textContent='Rekonsiliasi gagal: '+e.message}}
async function runPaymentSimulation(){const out=document.getElementById('pay-result');try{const cid=document.getElementById('pay-case').value;if(!cid){out.textContent='Masukkan Case ID.';return}const d=await api('/api/payment-instructions',{method:'POST',body:JSON.stringify({case_id:cid,provider_id:'PJP-SIM-001'})});out.innerHTML='<div class="feeditem"><b>'+esc(d.status)+'</b><br>Instruction: '+esc(d.instruction_id)+'<br>Executed: '+d.executed+'</div>'}catch(e){out.textContent='Payment simulation gagal.'}}
function togglePassword(){const input=document.getElementById('password');const btn=document.querySelector('.password-toggle');const visible=input.type==='text';input.type=visible?'password':'text';btn.setAttribute('aria-label',visible?'Tampilkan password':'Sembunyikan password');btn.setAttribute('title',visible?'Tampilkan password':'Sembunyikan password');document.getElementById('password-eye').innerHTML=visible?'<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"></path><circle cx="12" cy="12" r="2.5"></circle>':'<path d="M3 3l18 18"></path><path d="M10.6 6.2A10.8 10.8 0 0 1 12 6c6.5 0 10 6 10 6a18 18 0 0 1-4 4.2M6.2 6.8C3.4 8.4 2 12 2 12s3.5 6 10 6c1.5 0 2.8-.3 4-.8"></path><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"></path>'}async function login(){const msg=document.getElementById('msg');msg.textContent='Memverifikasi identitas...';try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:document.getElementById('email').value,password:document.getElementById('password').value})});const d=await r.json();if(!r.ok){msg.textContent=d.error==='unauthorized'?'Email atau password tidak cocok.':('Login gagal: '+(d.error||'unknown_error'));return}try{sessionStorage.setItem('vcmc_token',d.token)}catch(e){}token=d.token;await boot()}catch(e){msg.textContent='Koneksi gagal.'}}
async function logout(){try{await api('/api/logout',{method:'POST'})}catch(e){}sessionStorage.removeItem('vcmc_token');token=null;showLogin()}
window.showPublicLane=showPublicLane;window.submitPublicRequest=submitPublicRequest;window.togglePassword=togglePassword;window.login=login;window.logout=logout;window.go=go;window.room=room;
if(token)boot();
</script><script>
(function(){
  function bind(){
    var open=document.getElementById('public-open');
    var invited=document.getElementById('public-invited');
    var eye=document.getElementById('password-toggle');
    var loginBtn=document.getElementById('login-button');
    if(open) open.addEventListener('click',function(){showPublicLane('open')});
    if(invited) invited.addEventListener('click',function(){showPublicLane('invited')});
    if(eye) eye.addEventListener('click',togglePassword);
    if(loginBtn) loginBtn.addEventListener('click',login);
    var lane=document.getElementById('public-lane');
    if(lane) lane.addEventListener('click',function(e){
      var close=e.target.closest('[data-public-close]');
      if(close){ lane.innerHTML=''; return; }
      var submit=e.target.closest('[data-public-submit]');
      if(submit){ submitPublicRequest(submit.getAttribute('data-public-submit')); }
    });
  }
  document.addEventListener('pointerup',function(e){var t=e.target.closest('#public-open,#public-invited,#password-toggle,#login-button');if(t){if(t.id==='public-open')showPublicLane('open');else if(t.id==='public-invited')showPublicLane('invited');else if(t.id==='password-toggle')togglePassword();else if(t.id==='login-button')login();}}); if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',bind); else bind();
})();
</script><script>(function(){if(window.__vcmcRoomFallbackInstalled)return;window.__vcmcRoomFallbackInstalled=true;function e(x){return String(x==null?'':x).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}async function b(){try{var a=await fetch('/api/me',{credentials:'same-origin'}),h=await fetch('/api/home',{credentials:'same-origin'});if(!a.ok||!h.ok)throw Error('session');window.__vcmcMe=await a.json();window.__vcmcHome=await h.json();document.getElementById('login').classList.add('hidden');document.getElementById('app').classList.remove('hidden');document.getElementById('nav').classList.remove('hidden');window.__vcmcLobby()}catch(x){console.error(x)}}window.__vcmcLobby=function(){var h=window.__vcmcHome||{rooms:[]},m=window.__vcmcMe||{},rs=h.rooms||[];document.getElementById('title').textContent='Lobby';document.getElementById('content').innerHTML='<div class="card hero"><div class="eyebrow">VCMC-VP · LOBBY</div><h2>Selamat datang</h2><p class="muted">Sesi aktif · '+e(m.role||'')+'</p></div><section class="sectionhead"><h3>VCMC Rooms</h3><span>'+rs.length+' rooms</span></section><div class="rooms">'+rs.map(function(r){return '<button class="room" type="button" data-vroom="'+e(r.id)+'" style="text-align:left;color:inherit"><b>'+e(r.name)+'</b><br><small>'+e(r.status)+'</small></button>'}).join('')+'</div>';document.querySelectorAll('[data-vroom]').forEach(function(x){x.addEventListener('click',function(){window.__vcmcRoom(x.getAttribute('data-vroom'))})})};window.__vcmcRoom=function(id){
  var h=window.__vcmcHome||{rooms:[]},r=(h.rooms||[]).find(function(x){return x.id===id});
  if(!r)return;
  var c=document.getElementById('content'),t=document.getElementById('title');
  if(t)t.textContent=r.name;
  if(id==='architecture'){
    c.innerHTML='<div class="card hero"><button class="back" type="button" onclick="window.__vcmcLobby()">← Kembali ke Lobi</button><div class="eyebrow">VCMC ROOM · FUNCTIONAL</div><h2>Arsitektur</h2><p class="muted">Pilih bagian arsitektur untuk membuka detail.</p></div><div class="rooms"><button class="room" type="button" data-ar="foundation"><b>Identity / Foundation</b><br><small>TAQDA · Vision · Principles</small></button><button class="room" type="button" data-ar="governance"><b>Governance</b><br><small>Authority · Boundaries · Accountability</small></button><button class="room" type="button" data-ar="evidence"><b>Evidence</b><br><small>Proof · Verification · Audit</small></button><button class="room" type="button" data-ar="reconciliation"><b>Reconciliation</b><br><small>Expected · Actual · Ledger</small></button><button class="room" type="button" data-ar="network"><b>Global Network</b><br><small>Cross-border · Interaction</small></button><button class="room" type="button" data-ar="development"><b>Development</b><br><small>Need · Direction · Result</small></button></div>';
    document.querySelectorAll('[data-ar]').forEach(function(x){x.addEventListener('click',function(){
      var m={foundation:['Identity / Foundation','TAQDA → VCMC → Real Development → Real Benefit → Global Scale'],governance:['Governance','MENENTUKAN ≠ MENGHITUNG ≠ MEMEGANG DANA ≠ MEMBAYAR ≠ MENERIMA'],evidence:['Evidence','CLAIM → RECORDED → EVIDENCE SUBMITTED → VERIFIED → RECONCILED → PROVEN'],reconciliation:['Reconciliation','Amount → Destination → Purpose → Responsible Party → Evidence → Result → Reconciliation'],network:['Global Network','Identify → Screen → Classify → Route → Authorize → Interact → Evidence → Reconcile'],development:['Development','Need → Direction → Priority → Program → Project → Pilot → Result → Real Benefit']}[x.getAttribute('data-ar')]||['Architecture','VCMC Architecture'];
      c.innerHTML='<div class="card hero"><button class="back" type="button" onclick="window.__vcmcRoom(\'architecture\')">← Kembali ke Arsitektur</button><div class="eyebrow">ARCHITECTURE DETAIL</div><h2>'+m[0]+'</h2><p class="muted">'+m[1]+'</p></div><div class="card detail"><b>Boundary</b><p class="muted">Informasi ini adalah detail arsitektur. Authority dan proof tetap terpisah dan harus dibuktikan melalui tindakan yang berwenang.</p></div>';
    })});
    return;
  }
  c.innerHTML='<div class="card hero"><button class="back" type="button" onclick="window.__vcmcLobby()">← Kembali ke Lobi</button><div class="eyebrow">VCMC ROOM</div><h2>'+esc(r.name)+'</h2><p class="muted">Status: '+esc(r.status)+'</p></div><div class="card detail"><b>Fungsi</b><p class="muted">Room '+esc(r.id)+' tersedia. Fungsi operasional berikutnya harus dibuka melalui API dan authority yang sesuai.</p></div>';
};;var lo=document.querySelector('#app .logout');if(lo){lo.onclick=function(ev){ev.preventDefault();fetch('/api/logout',{method:'POST',credentials:'same-origin'}).finally(function(){try{sessionStorage.removeItem('vcmc_token')}catch(e){};document.getElementById('app').classList.add('hidden');document.getElementById('nav').classList.add('hidden');document.getElementById('login').classList.remove('hidden')})}}if(!window.boot)window.boot=b;if(!window.go)window.go=function(t){window.__vcmcLobby()};if(!window.room)window.room=function(id){window.__vcmcRoom(id)}})();</script></body></html>'''
   b=html.encode(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b); return
  if p=='/health': return self.sendj(200,{'status':'ok','machine':'VCMC-VP','real_money_enabled':REAL_MONEY})
  if p=='/api/system/readiness':
   c=conn(); provider=bool(c.execute('SELECT 1 FROM providers WHERE execution_verified=1').fetchone()); c.close(); return self.sendj(200,{'ready':not REAL_MONEY,'database':True,'public':True,'real_money':REAL_MONEY,'real_money_enabled':REAL_MONEY,'real_pjp_execution_verified':provider,'rule_id':RULE_ID,'rule_version':RULE_VERSION,'formula_version':FORMULA_VERSION})
  if p=='/api/rule': return self.sendj(200,{'rule_id':RULE_ID,'version':RULE_VERSION,'formula_version':FORMULA_VERSION})
  if p=='/api/public/presence':
   c=conn(); active=c.execute('SELECT COUNT(*) FROM sessions WHERE expires>?',(time.time(),)).fetchone()[0]; users=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]; partners=c.execute("SELECT COUNT(*) FROM partners WHERE status='PARTNER'").fetchone()[0]; projects=c.execute('SELECT COUNT(*) FROM projects').fetchone()[0]; c.close(); return self.sendj(200,{'live_now':active,'registered_users':users,'partners':partners,'projects':projects,'privacy':'aggregate_only','identities_exposed':False})
  if p=='/api/public/access-request':
   rid=urlparse(self.path).query
   if not rid.startswith('id='): return self.sendj(400,{'error':'id_required'})
   rid=rid[3:]; c=conn(); row=c.execute('SELECT id,request_type,name,organization,country,contact_type,language,status,created_at,updated_at FROM partner_access_requests WHERE id=?',(rid,)).fetchone(); c.close()
   if not row: return self.sendj(404,{'error':'request_not_found'})
   c=conn(); activation=bool(c.execute('SELECT 1 FROM access_activations WHERE request_id=? AND used=0 AND expires>?',(rid,time.time())).fetchone()); c.close(); result=dict(row); result['activation_ready']=activation; result['account_status']='not_available' if result['status'] not in {'CANDIDATE','PARTNER'} else ('activation_ready' if activation else 'account_ready_or_activated'); return self.sendj(200,{'request':result,'rule':'Registration != Approval · Login != Authority · Email != Partner'})
  if p=='/api/me':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   return self.sendj(200,{'authenticated':True,'id':user['id'],'name':user.get('name') or '','email':user['email'],'login_id':user.get('login_id') or '','role':user['role'],'status':user.get('status') or ('CREATOR' if user['role']=='SOVEREIGN' else user['role']),'context':user.get('session_context') or 'PUBLIC','session_active':True})
  if p=='/api/public/access-requests':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   if user.get('role')!='SOVEREIGN': return self.sendj(403,{'error':'sovereign_only'})
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,request_type,name,organization,country,contact_type,contact_value,language,message,status,created_at,updated_at FROM partner_access_requests ORDER BY created_at DESC')]; c.close(); return self.sendj(200,{'items':rows,'count':len(rows),'rule':'Registration != Approval · Login != Authority · Email != Partner'})
  if p=='/api/partners':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,name,kind,status,contact,created_at,updated_at FROM partners ORDER BY created_at DESC')]; c.close(); return self.sendj(200,{'items':rows,'count':len(rows),'rule':'Candidate != Pilot · READY != PROVEN'})
  if p=='/api/pilots':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,name,partner_id,status,objective,created_at,updated_at FROM pilots ORDER BY created_at DESC')]; c.close(); return self.sendj(200,{'items':rows,'count':len(rows),'rule':'Candidate != Pilot'})
  if p=='/api/projects':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,name,kind,status,pilot_id,created_at,updated_at FROM projects ORDER BY created_at DESC')]; c.close(); return self.sendj(200,{'items':rows,'count':len(rows)})
  if p=='/api/directions':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,name,priority,status,created_at,updated_at FROM directions ORDER BY created_at DESC')]; c.close(); return self.sendj(200,{'items':rows,'count':len(rows)})
  if p=='/api/capital-plans':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,name,purpose,status,amount,created_at,updated_at FROM capital_plans ORDER BY created_at DESC')]; c.close(); return self.sendj(200,{'items':rows,'count':len(rows),'boundary':'VCMC does not hold funds'})
  if p=='/api/network':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); entities=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]; relationships=c.execute('SELECT COUNT(*) FROM partners').fetchone()[0]; active_sessions=c.execute('SELECT COUNT(*) FROM sessions WHERE expires>?',(time.time(),)).fetchone()[0]; rows=[] if user.get('role')!='SOVEREIGN' else [dict(x) for x in c.execute('SELECT action,entity,at FROM audit ORDER BY id DESC LIMIT 8')]; c.close()
   return self.sendj(200,{'entities':entities,'relationships':relationships,'active_sessions':active_sessions,'activity':rows,'privacy':'aggregate_only' if user.get('role')!='SOVEREIGN' else 'internal'})
  if p=='/api/activity':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); rows=[dict(x) for x in c.execute('SELECT at,actor,action,entity,details FROM audit ORDER BY id DESC LIMIT 20')]; c.close(); return self.sendj(200,{'items':rows})
  if p=='/api/notifications':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   return self.sendj(200,{'items':[{'type':'control','title':'Evidence required','status':'attention'},{'type':'payment','title':'Payment execution','status':'simulation'}]})
  if p=='/api/home':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); metrics={'cases':c.execute('SELECT COUNT(*) FROM cases').fetchone()[0],'evidence':c.execute('SELECT COUNT(*) FROM evidence').fetchone()[0],'audit':c.execute('SELECT COUNT(*) FROM audit').fetchone()[0],'reconciliations':c.execute('SELECT COUNT(*) FROM reconciliations').fetchone()[0]}; c.close()
   sovereign_rooms=[{'id':'architecture','name':'Architecture','status':'available'},{'id':'network','name':'Global Network','status':'available'},{'id':'partners','name':'Partners & Candidates','status':'available'},{'id':'pilots','name':'Pilots','status':'available'},{'id':'projects','name':'Programs & Projects','status':'available'},{'id':'development','name':'Development Direction','status':'available'},{'id':'capital','name':'Capital & Development','status':'available'},{'id':'distribution','name':'Distribution','status':'available'},{'id':'evidence','name':'Evidence & Verification','status':'available'},{'id':'reconciliation','name':'Reconciliation','status':'available'},{'id':'security','name':'Security','status':'available'},{'id':'system','name':'System & Operations','status':'available'},{'id':'payment','name':'Payment / Providers','status':'simulation'}]
   external_rooms=[{'id':'partner-profile','name':'My VCMC Access','status':'active'},{'id':'partner-status','name':'Application Status','status':'active'},{'id':'partner-evidence','name':'My Evidence','status':'active'}]
   rooms=sovereign_rooms if user['role']=='SOVEREIGN' else external_rooms
   return self.sendj(200,{'identity':{'id':user['id'],'email':user['email'],'role':user['role']},'metrics':metrics,'system':{'real_money_enabled':REAL_MONEY},'rooms':rooms})
  if p=='/api/evidence':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,case_id,kind,sha256,created_at FROM evidence ORDER BY id DESC')]; c.close(); count=len(rows); verified=0; return self.sendj(200,{'items':rows,'count':count,'verified':verified,'unverified':count-verified})
  if p=='/api/reconciliation':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,case_id,status,expected,executed,received,ledger,created_at FROM reconciliations ORDER BY id DESC')]; c.close(); return self.sendj(200,{'items':rows,'count':len(rows)})
  if p=='/api/backups':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,path,sha256,created_at FROM backups ORDER BY id DESC')]; c.close(); return self.sendj(200,{'items':rows,'count':len(rows)})
  if p=='/api/metrics':
   c=conn(); n=c.execute('SELECT COUNT(*) FROM cases').fetchone()[0]; a=c.execute('SELECT COUNT(*) FROM audit').fetchone()[0]; c.close(); return self.sendj(200,{'cases':n,'audit_events':a})
  if p=='/api/api': return self.sendj(200,{'version':'v1','routes':['/api/login','/api/cases','/api/calculate','/api/allocate','/api/state','/api/evidence','/api/payment-instructions','/api/backups/create','/api/reconciliation','/api/metrics','/api/me','/api/home','/api/network','/api/activity','/api/notifications','/api/system/readiness']})
  if p=='/api/destinations':
   c=conn(); rows=[dict(x) for x in c.execute('SELECT id,label,kind,active FROM destinations')]; c.close(); return self.sendj(200,{'destinations':rows})
  return self.sendj(404,{'error':'not_found'})
 def do_POST(self):
  p=urlparse(self.path).path
  if self.headers.get('Content-Type','').startswith('application/x-www-form-urlencoded'):
   from urllib.parse import parse_qs
   raw=self.rfile.read(int(self.headers.get('Content-Length','0'))).decode()
   form=parse_qs(raw); data={k:v[0] for k,v in form.items()}
  else:
   try: data=self.body()
   except: return self.sendj(400,{'error':'invalid_json'})
  if p=='/api/login':
   email=str(data.get('email','')).strip(); password=str(data.get('password','')); context=str(data.get('context','PUBLIC')).strip().upper()
   allowed_contexts={'PUBLIC','INDIVIDUAL','PROFESSIONAL','ENTREPRENEUR','ORGANIZATION','CANDIDATE','PARTNER','CREATOR'}
   if context not in allowed_contexts: return self.sendj(400,{'error':'invalid_context'})
   hashed=hashlib.sha256(password.encode()).hexdigest()
   c=conn(); u=c.execute('SELECT * FROM users WHERE (email=? OR login_id=?) AND password_hash=?',(email,email,hashed)).fetchone()
   if not u and email==ADMIN_EMAIL and password==ADMIN_PASSWORD:
    row=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if row:
     u=row
    else:
     c.execute('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)',(ADMIN_EMAIL,hashed,'SOVEREIGN')); c.commit()
     u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
   if not u: c.close(); return self.sendj(401,{'error':'unauthorized'})
   if context=='CREATOR' and u['role']!='SOVEREIGN': c.close(); return self.sendj(403,{'error':'creator_context_requires_sovereign'})
   if context=='PARTNER' and u['role']!='PARTNER': c.close(); return self.sendj(403,{'error':'partner_context_requires_partner_status'})
   if context=='CANDIDATE' and u['role'] not in {'CANDIDATE','PARTNER'}: c.close(); return self.sendj(403,{'error':'candidate_context_requires_candidate_status'})
   tok=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions(token,user_id,expires,context) VALUES(?,?,?,?)',(tok,u['id'],time.time()+86400,context)); c.commit(); c.close(); audit(u['email'],'LOGIN','USER',u['email']+' / '+context)
   if self.headers.get('Content-Type','').startswith('application/x-www-form-urlencoded'):
    self.send_response(303); self.send_header('Set-Cookie','vcmc_token='+tok+'; Path=/; HttpOnly; SameSite=Lax'); self.send_header('Location','/'); self.end_headers(); return
   self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Set-Cookie','vcmc_token='+tok+'; Path=/; HttpOnly; SameSite=Lax'); body=json.dumps({'token':tok,'role':u['role'],'status':u['status'] if 'status' in u.keys() else ('CREATOR' if u['role']=='SOVEREIGN' else u['role']),'context':context}).encode(); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body); return
  if p=='/api/password/change':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   current=str(data.get('current_password','')); new_password=str(data.get('new_password',''))
   if len(new_password)<8: return self.sendj(400,{'error':'password_min_8_chars'})
   if hashlib.sha256(current.encode()).hexdigest()!=user['password_hash']: return self.sendj(401,{'error':'current_password_incorrect'})
   if current==new_password: return self.sendj(400,{'error':'new_password_must_differ'})
   hashed=hashlib.sha256(new_password.encode()).hexdigest(); c=conn()
   c.execute('UPDATE users SET password_hash=? WHERE id=?',(hashed,user['id'])); c.commit(); c.close()
   audit(user['email'],'PASSWORD_CHANGE','USER',user['email'])
   return self.sendj(200,{'ok':True,'status':'password_changed'})
  if p=='/api/account/update':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   current=str(data.get('current_password',''))
   if hashlib.sha256(current.encode()).hexdigest()!=user['password_hash']: return self.sendj(401,{'error':'current_password_incorrect'})
   new_email=str(data.get('email',user['email'])).strip().lower(); new_name=str(data.get('name',user.get('name') or '')).strip()
   if not new_email or '@' not in new_email: return self.sendj(400,{'error':'valid_email_required'})
   c=conn(); other=c.execute('SELECT id FROM users WHERE email=? AND id<>?',(new_email,user['id'])).fetchone()
   if other: c.close(); return self.sendj(409,{'error':'email_in_use'})
   c.execute('UPDATE users SET email=?,name=? WHERE id=?',(new_email,new_name,user['id'])); c.commit(); c.close()
   audit(user['email'],'ACCOUNT_UPDATE','USER',user['email'])
   return self.sendj(200,{'ok':True,'email':new_email,'name':new_name,'login_id':user.get('login_id'),'role':user['role']})
  if p=='/api/sessions/revoke-other':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   auth=self.headers.get('Authorization','').strip(); current=auth[7:].strip() if auth.lower().startswith('bearer ') else ''
   if not current:
    ck=self.headers.get('Cookie','')
    for part in ck.split(';'):
     if part.strip().startswith('vcmc_token='): current=part.strip().split('=',1)[1]; break
   c=conn(); c.execute('DELETE FROM sessions WHERE user_id=? AND token<>?',(user['id'],current)); n=c.total_changes; c.commit(); c.close()
   audit(user['email'],'REVOKE_OTHER_SESSIONS','USER',user['email'])
   return self.sendj(200,{'ok':True,'revoked_sessions':n})
  if p=='/api/public/register':
   email=str(data.get('email','')).strip().lower(); password=str(data.get('password','')); name=str(data.get('name','')).strip(); context=str(data.get('context','CANDIDATE')).strip().upper()
   if context not in {'INDIVIDUAL','PROFESSIONAL','ENTREPRENEUR','ORGANIZATION','CANDIDATE'}: return self.sendj(400,{'error':'invalid_registration_context'})
   if not name or not email or '@' not in email: return self.sendj(400,{'error':'name_and_valid_email_required'})
   if len(password)<8: return self.sendj(400,{'error':'password_min_8_chars'})
   hashed=hashlib.sha256(password.encode()).hexdigest(); c=conn()
   if c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(): c.close(); return self.sendj(409,{'error':'account_exists'})
   login_id='CAND-'+secrets.token_hex(5).upper()
   c.execute('INSERT INTO users(email,login_id,password_hash,role,status,name) VALUES(?,?,?,?,?,?)',(email,login_id,hashed,'PUBLIC','PUBLIC',name)); uid=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()['id']
   tok=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions(token,user_id,expires,context) VALUES(?,?,?,?)',(tok,uid,time.time()+86400,context)); c.commit(); c.close(); audit(email,'SELF_REGISTER','USER','PUBLIC / '+context)
   self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Set-Cookie','vcmc_token='+tok+'; Path=/; HttpOnly; SameSite=Lax'); body=json.dumps({'token':tok,'role':'PUBLIC','status':'PUBLIC','email':email,'login_id':login_id,'name':name,'context':context}).encode(); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body); return
  if p=='/api/public/access-requests/review':
   user=self.auth()
   if not user: return self.sendj(401,{'error':'unauthorized'})
   if user.get('role')!='SOVEREIGN': return self.sendj(403,{'error':'sovereign_only'})
   rid=str(data.get('id','')).strip(); status=str(data.get('status','')).strip().upper()
   allowed={'REQUESTED','SCREENING','CANDIDATE','PARTNER','HOLD','REJECTED'}
   if status not in allowed: return self.sendj(400,{'error':'invalid_status'})
   c=conn(); row=c.execute('SELECT * FROM partner_access_requests WHERE id=?',(rid,)).fetchone()
   if not row: c.close(); return self.sendj(404,{'error':'request_not_found'})
   stamp=now(); c.execute('UPDATE partner_access_requests SET status=?,updated_at=? WHERE id=?',(status,stamp,rid)); partner_id=None; activation_code=None
   if status in {'CANDIDATE','PARTNER'}:
    existing=c.execute('SELECT id FROM partners WHERE contact=? LIMIT 1',(row['contact_value'],)).fetchone()
    if existing:
     partner_id=existing['id']; c.execute('UPDATE partners SET kind=?,status=?,updated_at=? WHERE id=?',('PARTNER' if status=='PARTNER' else 'CANDIDATE',status,stamp,partner_id))
    else:
     partner_id=('PARTNER-' if status=='PARTNER' else 'CANDIDATE-')+secrets.token_hex(6); c.execute('INSERT INTO partners(id,name,kind,status,contact,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(partner_id,row['name'],'PARTNER' if status=='PARTNER' else 'CANDIDATE',status,row['contact_value'],stamp,stamp))
    if row['contact_type']=='email':
     activation_code=issue_activation(c,rid,row['contact_value'].lower(),external_role(status))
     existing_user=c.execute('SELECT id FROM users WHERE email=?',(row['contact_value'].lower(),)).fetchone()
     if existing_user and existing_user['role']!='SOVEREIGN': c.execute('UPDATE users SET role=?,status=? WHERE id=?',(external_role(status),status,existing_user['id']))
   else:
    c.execute('DELETE FROM access_activations WHERE request_id=? AND used=0',(rid,))
   c.commit(); c.close(); audit(user['email'],'REVIEW_ACCESS_REQUEST',rid,status)
   result={'id':rid,'status':status,'partner_id':partner_id}
   if activation_code: result['activation_code']=activation_code; result['activation_expires_days']=7
   return self.sendj(200,result)
  if p=='/api/public/access-requests':
   name=str(data.get('name','')).strip(); org=str(data.get('organization','')).strip(); country=str(data.get('country','')).strip(); language=str(data.get('language','en')).strip().lower(); contact_type=str(data.get('contact_type','phone')).strip().lower(); contact_value=str(data.get('contact_value','')).strip(); message=str(data.get('message','')).strip(); request_type=str(data.get('request_type','open')).strip().lower()
   if not name: return self.sendj(400,{'error':'name_required'})
   if not contact_value: return self.sendj(400,{'error':'one_contact_method_required'})
   if contact_type not in {'phone','email'}: return self.sendj(400,{'error':'invalid_contact_type'})
   if request_type not in {'open','invited'}: return self.sendj(400,{'error':'invalid_request_type'})
   if language not in {'id','en','ar','es','fr'}: return self.sendj(400,{'error':'invalid_language'})
   rid='ACCESS-'+secrets.token_hex(6); stamp=now(); c=conn(); c.execute('INSERT INTO partner_access_requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,request_type,name,org,country,contact_type,contact_value,language,message,'REQUESTED',stamp,stamp)); c.commit(); c.close(); audit('PUBLIC','REQUEST_ACCESS',rid,request_type+' / '+language); return self.sendj(201,{'id':rid,'status':'REQUESTED','request_type':request_type,'language':language,'next':'VCMC screening / review'})
  if p=='/api/public/activate':
   rid=str(data.get('request_id','')).strip(); code=str(data.get('activation_code','')).strip(); password=str(data.get('password',''))
   if not rid or not code or len(password)<8: return self.sendj(400,{'error':'request_id_activation_code_and_8_char_password_required'})
   c=conn(); a=c.execute('SELECT * FROM access_activations WHERE code=? AND request_id=? AND used=0 AND expires>?',(code,rid,time.time())).fetchone(); row=c.execute('SELECT * FROM partner_access_requests WHERE id=?',(rid,)).fetchone()
   if not a or not row or row['status'] not in {'CANDIDATE','PARTNER'} or row['contact_type']!='email' or row['contact_value'].lower()!=a['email'].lower():
    c.close(); return self.sendj(403,{'error':'invalid_or_expired_activation'})
   email=a['email'].lower(); hashed=hashlib.sha256(password.encode()).hexdigest(); existing=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
   if existing:
    if existing['role']=='SOVEREIGN': c.close(); return self.sendj(409,{'error':'email_reserved'})
    c.execute('UPDATE users SET password_hash=?,role=?,status=? WHERE id=?',(hashed,external_role(row['status']),row['status'],existing['id'])); uid=existing['id']
   else:
    c.execute('INSERT INTO users(email,password_hash,role,status) VALUES(?,?,?,?)',(email,hashed,external_role(row['status']),row['status'])); uid=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()['id']
   c.execute('UPDATE access_activations SET used=1 WHERE code=?',(code,)); tok=secrets.token_urlsafe(32); activation_context=external_role(row['status']); c.execute('INSERT INTO sessions(token,user_id,expires,context) VALUES(?,?,?,?)',(tok,uid,time.time()+86400,activation_context)); c.commit(); c.close(); audit(email,'ACTIVATE_ACCOUNT',rid,activation_context)
   self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Set-Cookie','vcmc_token='+tok+'; Path=/; HttpOnly; SameSite=Lax'); body=json.dumps({'token':tok,'role':external_role(row['status']),'email':email}).encode(); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body); return
  if p=='/api/logout':
   t=self.headers.get('Authorization','').replace('Bearer ','').strip()
   if not t:
    ck=self.headers.get('Cookie','')
    for part in ck.split(';'):
     if part.strip().startswith('vcmc_token='): t=part.strip().split('=',1)[1]; break
   c=conn()
   if t: c.execute('DELETE FROM sessions WHERE token=?',(t,)); c.commit()
   c.close()
   self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Set-Cookie','vcmc_token=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax'); body=json.dumps({'logged_out':True}).encode(); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body); return
  user=self.auth()
  if not user: return self.sendj(401,{'error':'unauthorized'})
  if p=='/api/partners':
   name=str(data.get('name','')).strip(); kind=str(data.get('kind','CANDIDATE')).strip().upper(); status=str(data.get('status','CANDIDATE')).strip().upper(); contact=str(data.get('contact','')).strip()
   if not name: return self.sendj(400,{'error':'name_required'})
   if kind not in {'CANDIDATE','PARTNER'}: return self.sendj(400,{'error':'invalid_kind'})
   if status not in {'CANDIDATE','SCREENING','READY','HOLD','UNKNOWN'}: return self.sendj(400,{'error':'invalid_status'})
   pid='PARTNER-'+secrets.token_hex(6); stamp=now(); c=conn(); c.execute('INSERT INTO partners(id,name,kind,status,contact,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(pid,name,kind,status,contact,stamp,stamp)); c.commit(); c.close(); audit(user['email'],'REGISTER_PARTNER',pid,kind+' / '+status); return self.sendj(201,{'id':pid,'name':name,'kind':kind,'status':status,'contact':contact,'created_at':stamp})
  if p=='/api/pilots':
   name=str(data.get('name','')).strip(); partner_id=str(data.get('partner_id','')).strip(); status=str(data.get('status','PILOT_CANDIDATE')).strip().upper(); objective=str(data.get('objective','')).strip()
   if not name: return self.sendj(400,{'error':'name_required'})
   if status not in {'PILOT_CANDIDATE','SCREENING','READY','ACTIVE','HOLD','UNKNOWN'}: return self.sendj(400,{'error':'invalid_status'})
   pid='PILOT-'+secrets.token_hex(6); stamp=now(); c=conn(); c.execute('INSERT INTO pilots VALUES(?,?,?,?,?,?,?)',(pid,name,partner_id,status,objective,stamp,stamp)); c.commit(); c.close(); audit(user['email'],'REGISTER_PILOT',pid,status); return self.sendj(201,{'id':pid,'name':name,'partner_id':partner_id,'status':status,'objective':objective,'created_at':stamp})
  if p=='/api/projects':
   name=str(data.get('name','')).strip(); kind=str(data.get('kind','PROJECT')).strip().upper(); status=str(data.get('status','DRAFT')).strip().upper(); pilot_id=str(data.get('pilot_id','')).strip()
   if not name: return self.sendj(400,{'error':'name_required'})
   if kind not in {'PROGRAM','PROJECT'}: return self.sendj(400,{'error':'invalid_kind'})
   if status not in {'DRAFT','PLANNING','ACTIVE','HOLD','COMPLETED','UNKNOWN'}: return self.sendj(400,{'error':'invalid_status'})
   xid='PROJECT-'+secrets.token_hex(6); stamp=now(); c=conn(); c.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?)',(xid,name,kind,status,pilot_id,stamp,stamp)); c.commit(); c.close(); audit(user['email'],'REGISTER_PROJECT',xid,kind+' / '+status); return self.sendj(201,{'id':xid,'name':name,'kind':kind,'status':status,'pilot_id':pilot_id,'created_at':stamp})
  if p=='/api/directions':
   name=str(data.get('name','')).strip(); priority=str(data.get('priority','NORMAL')).strip().upper(); status=str(data.get('status','PROPOSED')).strip().upper()
   if not name: return self.sendj(400,{'error':'name_required'})
   if priority not in {'LOW','NORMAL','HIGH','CRITICAL'}: return self.sendj(400,{'error':'invalid_priority'})
   if status not in {'PROPOSED','REVIEW','AUTHORIZED','HOLD','UNKNOWN'}: return self.sendj(400,{'error':'invalid_status'})
   did='DIR-'+secrets.token_hex(6); stamp=now(); c=conn(); c.execute('INSERT INTO directions VALUES(?,?,?,?,?,?)',(did,name,priority,status,stamp,stamp)); c.commit(); c.close(); audit(user['email'],'REGISTER_DIRECTION',did,priority+' / '+status); return self.sendj(201,{'id':did,'name':name,'priority':priority,'status':status,'created_at':stamp})
  if p=='/api/capital-plans':
   name=str(data.get('name','')).strip(); purpose=str(data.get('purpose','')).strip(); status=str(data.get('status','PLANNED')).strip().upper(); amount=int(data.get('amount',0) or 0)
   if not name or not purpose: return self.sendj(400,{'error':'name_and_purpose_required'})
   if amount<0: return self.sendj(400,{'error':'invalid_amount'})
   if status not in {'PLANNED','REVIEW','AUTHORIZED','HOLD','UNKNOWN'}: return self.sendj(400,{'error':'invalid_status'})
   cid='CAP-'+secrets.token_hex(6); stamp=now(); c=conn(); c.execute('INSERT INTO capital_plans VALUES(?,?,?,?,?,?,?)',(cid,name,purpose,status,amount,stamp,stamp)); c.commit(); c.close(); audit(user['email'],'REGISTER_CAPITAL_PLAN',cid,status); return self.sendj(201,{'id':cid,'name':name,'purpose':purpose,'status':status,'amount':amount,'created_at':stamp})

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
   cid=data.get('case_id','').strip()
   if not cid: return self.sendj(400,{'error':'case_id_required'})
   vals=[int(data.get(k,0)) for k in ('expected','executed','received','ledger')]; status='RECONCILED' if len(set(vals))==1 else 'EXCEPTION'; c=conn(); c.execute('INSERT INTO reconciliations(case_id,status,expected,executed,received,ledger,created_at) VALUES(?,?,?,?,?,?,?)',(cid,status,*vals,now())); c.commit(); c.close(); audit(user['email'],'RECONCILE',cid,status); return self.sendj(200,{'case_id':cid,'status':status,'expected':vals[0],'executed':vals[1],'received':vals[2],'ledger':vals[3]})
  if p=='/api/backups/create':
   os.makedirs(BACKUP_DIR,exist_ok=True); target=os.path.join(BACKUP_DIR,'vcmp-'+str(int(time.time()))+'.db'); shutil.copy2(DB,target); h=hashlib.sha256(open(target,'rb').read()).hexdigest(); c=conn(); c.execute('INSERT INTO backups(path,sha256,created_at) VALUES(?,?,?)',(target,h,now())); c.commit(); c.close(); audit(user['email'],'BACKUP','SYSTEM',h); return self.sendj(200,{'path':target,'sha256':h})
  return self.sendj(404,{'error':'not_found'})
if __name__=='__main__': init(); ThreadingHTTPServer((HOST,PORT),H).serve_forever()