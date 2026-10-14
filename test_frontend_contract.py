import os,re,subprocess,tempfile,shutil
from html.parser import HTMLParser

ROOT=os.path.dirname(os.path.abspath(__file__))
HTML_PATH=os.path.join(ROOT,'docs','index.html')
class CheckHTML(HTMLParser):
 def __init__(self):
  super().__init__(); self.ids=[]; self.inline=[]; self._script=False; self._current=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if 'id' in attrs:self.ids.append(attrs['id'])
  if tag=='script' and not attrs.get('src'):
   self._script=True; self._current=[]
 def handle_data(self,data):
  if self._script:self._current.append(data)
 def handle_endtag(self,tag):
  if tag=='script' and self._script:
   self.inline.append(''.join(self._current)); self._script=False; self._current=[]

with open(HTML_PATH,encoding='utf-8') as f: html=f.read()
p=CheckHTML(); p.feed(html); p.close()
required_rooms=['architecture','network','partners','pilots','projects','development','capital','distribution','evidence','reconciliation','security','system','payment']
for room in required_rooms:
 assert re.search(r"id\s*:\s*['\"]"+re.escape(room)+r"['\"]",html), 'missing room: '+room
for required in ['Universal Global Development Architecture','TAQDA','REAL_MONEY','Request / Invitation','IDENTITY & SESSION','Evidence & Verification','Reconciliation','Payment / Providers','Change password','Logout','/api/system/readiness','/api/public/access-requests']:
 assert required in html, 'missing frontend contract: '+required
assert 'vcmc_api_base' in html, 'backend URL must be configurable'
assert 'class="tile tile-action" onclick="go(' in html, 'Home shortcuts must be clickable navigation controls'
assert 'Navigasi lintas-ruang' in html, 'Rooms must expose connected-room navigation'
assert 'Status ini adalah status implementasi' in html or 'bukan bukti bahwa backend atau operasi nyata telah lulus' in html, 'Room status must not imply operational proof'
assert 'password' in html.lower() and 'autocomplete="current-password"' in html, 'password UX missing'
assert 'Payment instruction only' in html or 'simulation' in html.lower(), 'payment simulation boundary missing'
assert 'REAL_MONEY_ENABLED=true' not in html, 'frontend must not enable real money'
node=shutil.which('node')
if node:
 with tempfile.NamedTemporaryFile('w',suffix='.js',encoding='utf-8',delete=False) as f:
  f.write('\n'.join(p.inline)); js_path=f.name
 try:
  result=subprocess.run([node,'--check',js_path],capture_output=True,text=True)
  assert result.returncode==0, 'inline JavaScript syntax error:\n'+result.stderr
 finally: os.unlink(js_path)
print('VCMC-VP FRONTEND CONTRACT TEST: PASS')
