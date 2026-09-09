"""Local workspace extensions: public feeds, provider telemetry and tool jobs."""
import concurrent.futures
import datetime as dt
import json
import os
from pathlib import Path
import re
import select
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from utils import live_bar, osint_casebook, news_markets

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
REPOS = HOME / 'Documents/ChatGPT' / "Repo's"
CACHE = {}
LOCK = threading.RLock()
JOBS = {}
POOL = concurrent.futures.ThreadPoolExecutor(max_workers=8)


def get_json(url, timeout=9):
    req = urllib.request.Request(url, headers={'User-Agent':'U1OS/2.0 (local personal dashboard)', 'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def cached(key, seconds, loader):
    with LOCK:
        old = CACHE.get(key)
        if old and time.time() - old['checked_at'] < seconds:
            return old
    try:
        value = loader()
        value.update(checked_at=time.time(), stale=False)
    except Exception as exc:
        value = dict(old or {})
        value.update(success=False, stale=bool(old), checked_at=time.time(), error=type(exc).__name__ + ': provider unavailable')
    with LOCK:
        CACHE[key] = value
    return value


def weather(city='Melbourne'):
    city = city.strip()[:100] or 'Melbourne'
    def load():
        geo = get_json('https://geocoding-api.open-meteo.com/v1/search?' + urllib.parse.urlencode({'name':city,'count':1,'language':'en','format':'json'}))
        matches = geo.get('results', [])
        if not matches:
            return {'success':False,'error':'City not found. Try a larger nearby town.'}
        place = matches[0]
        query = {'latitude':place['latitude'],'longitude':place['longitude'],'current':'temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m','hourly':'temperature_2m,precipitation_probability','daily':'weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max','timezone':'auto','forecast_days':7}
        data = get_json('https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(query))
        return dict(success=True,city=place['name'],region=place.get('admin1',''),country=place.get('country',''),source='Open-Meteo',source_url='https://open-meteo.com/',**data)
    return cached('weather:'+city.casefold(),600,load)


def normalize_espn(data):
    events = data.get('events', [])
    if not events:
        for sport in data.get('sports', []):
            for league in sport.get('leagues', []):
                events.extend(league.get('events', []))
    rows=[]
    for event in events:
        competitions=event.get('competitions') or [event]
        for comp in competitions[:20]:
            status=comp.get('status') or event.get('status') or {}
            if isinstance(status,str):
                state=status.lower();detail=event.get('summary') or status
            else:
                typ=status.get('type',{});state=typ.get('state','pre');detail=typ.get('shortDetail') or typ.get('detail') or status.get('detail','Scheduled')
            teams=[]
            for team in comp.get('competitors',[]):
                identity=team.get('team') or team.get('athlete') or team
                score=team.get('score')
                if isinstance(score,dict):score=score.get('displayValue',score.get('value'))
                teams.append(dict(name=identity.get('displayName') or identity.get('name') or team.get('name','TBA'),score=str(score) if score is not None else None,winner=team.get('winner',False)))
            rows.append(dict(id=str(comp.get('id',event.get('id',''))),name=event.get('name') or event.get('shortName','Event'),date=comp.get('date') or event.get('date'),state=state,status=detail,competitors=teams,venue=(comp.get('venue') or {}).get('fullName','')))
    return rows[:60]


def sports(kind):
    if kind not in {'afl','cricket','mma','boxing'}:
        raise ValueError('Unknown sport')
    def load():
        if kind=='afl':
            year=dt.datetime.now().year
            data=get_json('https://api.squiggle.com.au/?q=games;year='+str(year))
            games=data.get('games',[])
            today=dt.datetime.now().strftime('%Y-%m-%d')
            games=sorted(games,key=lambda g:abs((dt.date.fromisoformat(g['date'][:10])-dt.date.fromisoformat(today)).days))[:12]
            rows=[dict(id=str(g['id']),name=g['hteam']+' vs '+g['ateam'],date=g.get('date'),state='post' if g.get('complete')==100 else ('in' if 0<(g.get('complete') or 0)<100 else 'pre'),status=g.get('timestr') or ('Full time' if g.get('complete')==100 else 'Scheduled'),competitors=[dict(name=g['hteam'],score=g.get('hscore') if g.get('complete') else None),dict(name=g['ateam'],score=g.get('ascore') if g.get('complete') else None)],venue=g.get('venue','')) for g in games]
            return dict(success=True,events=rows,source='Squiggle AFL',source_url='https://squiggle.au/')
        routes={'mma':'https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard','boxing':'https://site.api.espn.com/apis/site/v2/sports/boxing/boxing/scoreboard','cricket':'https://site.web.api.espn.com/apis/personalized/v2/scoreboard/header?sport=cricket'}
        data=get_json(routes[kind])
        return dict(success=True,events=normalize_espn(data),source='ESPN',source_url={'mma':'https://www.espn.com/mma/scoreboard','boxing':'https://www.espn.com/boxing/','cricket':'https://www.espncricinfo.com/live-cricket-score'}[kind],notice='Public feed; coverage and availability depend on the provider.')
    return cached('sports:'+kind,45,load)


def codex_limits():
    executable=HOME/'.local/bin/codex'
    if not executable.exists():
        return dict(success=False,error='Codex CLI is not installed',windows=[])
    proc=subprocess.Popen([str(executable),'app-server','--stdio'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    buffer=b''
    deadline=time.monotonic()+15
    def send(message):
        proc.stdin.write((json.dumps(message)+'\n').encode());proc.stdin.flush()
    def receive(request_id):
        nonlocal buffer
        while time.monotonic()<deadline:
            while b'\n' in buffer:
                line,buffer=buffer.split(b'\n',1)
                try:msg=json.loads(line)
                except ValueError:continue
                if msg.get('id')==request_id:return msg
            ready,_,_=select.select([proc.stdout],[],[],.25)
            if ready:
                block=os.read(proc.stdout.fileno(),65536)
                if not block:break
                buffer+=block
        raise TimeoutError('Usage request timed out')
    try:
        send({'id':0,'method':'initialize','params':{'clientInfo':{'name':'u1_os','title':'U1 OS usage','version':'2.0'}}})
        receive(0)
        send({'method':'initialized','params':{}})
        send({'id':1,'method':'account/rateLimits/read','params':{}})
        reply=receive(1)
        if 'error' in reply:return dict(success=False,error='Sign in to Codex to read account limits.',windows=[])
        result=reply.get('result',{})
        from utils.u1_usage_windows import normalize_rate_limits
        return dict(success=True,windows=normalize_rate_limits(result),primary_limit_id='codex',source='Codex account/rateLimits/read')
    finally:
        proc.terminate()
        try:proc.wait(timeout=2)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()


def claude_activity():
    files=sorted((HOME/'.claude/projects').glob('*/*.jsonl'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]
    records={}; cutoff=time.time()-86400
    for path in files:
        if path.stat().st_mtime<cutoff:continue
        with path.open('rb') as stream:
            size=path.stat().st_size
            if size>5_000_000:stream.seek(size-5_000_000);stream.readline()
            for line in stream:
                try:
                    item=json.loads(line);message=item.get('message',{});usage=message.get('usage') or {}
                    stamp=dt.datetime.fromisoformat(item.get('timestamp','').replace('Z','+00:00')).timestamp()
                    if stamp<cutoff or not usage:continue
                    ident=message.get('id') or item.get('uuid')
                    amount=sum(int(usage.get(k,0) or 0) for k in ['input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens'])
                    records[ident]=max(records.get(ident,0),amount)
                except (ValueError,TypeError,AttributeError):continue
    return dict(success=True,local_tokens_24h=sum(records.values()),local_messages_24h=len(records),quota_available=False,source='Local Claude Code session usage',notice='Local activity only. Subscription allowance is available in Claude Settings > Usage.',url='https://claude.ai/settings/usage')


def antigravity_activity():
    paths=sorted((HOME/'.gemini/antigravity-ide/conversations').glob('*.db'),key=lambda p:p.stat().st_mtime,reverse=True)
    result=dict(success=True,quota_available=False,source='Local Antigravity session status',notice='Antigravity does not expose a verified quota reader here. Check account limits in the app.',url='https://antigravity.google/')
    if not paths:return result
    path=paths[0];result['last_activity']=path.stat().st_mtime
    try:
        with sqlite3.connect('file:'+urllib.parse.quote(str(path))+'?mode=ro',uri=True,timeout=1) as db:
            rows=db.execute('SELECT step_payload FROM steps WHERE step_type=17 ORDER BY idx DESC LIMIT 12').fetchall()
        for (blob,) in rows:
            text=bytes(blob).decode('utf-8','ignore')
            match=re.search(r'quotaResetTimeStamp.{0,15}?(20\d\d-\d\d-\d\dT[0-9:]+Z)',text)
            if match:
                result['last_reported_reset']=match.group(1);result['notice']='Last local quota-limit event recorded. This is not a current allowance percentage.';break
    except sqlite3.Error:pass
    return result


def usage():
    loaders={'codex':codex_limits,'claude':claude_activity,'antigravity':antigravity_activity}
    futures={key:POOL.submit(cached,'usage:'+key,60,loader) for key,loader in loaders.items()}
    return dict(success=True,providers={key:future.result() for key,future in futures.items()})


TOOLS=[
    dict(id='sherlock',name='Sherlock',kind='cli',description='Username discovery across public websites.'),
    dict(id='maigret',name='Maigret',kind='web',port=4176,app='Maigret',description='Public profile research and reports.'),
    dict(id='spiderfoot',name='SpiderFoot',kind='web',port=5001,app='SpiderFoot',description='Automated open-source intelligence workspace.'),
    dict(id='gods-eye-view',name="God's Eye View",kind='web',port=4174,app='Gods Eye View',description='Geospatial intelligence and public data.'),
    dict(id='osiris',name='Osiris AI',kind='web',port=4175,app='Osiris AI',description='Research and AI workspace.'),
    dict(id='holehe',name='Holehe',kind='cli',description='Email registration checks for authorized research.'),
    dict(id='dfw1n-osint',name='DFW1N OSINT',kind='guide',description='Australian OSINT resource directory.'),
    dict(id='ponytail',name='Ponytail',kind='guide',description='Agent development helper, not an OSINT scanner.'),
]


def tools_status():
    rows=[]
    for spec in TOOLS:
        item=dict(spec);repo=REPOS/item['id'];item['installed']=repo.is_dir();item['path']=str(repo);item['running']=False
        desktop_name=spec.get('app') or {'sherlock':'Sherlock','dfw1n-osint':'DFW1N OSINT'}.get(item['id'])
        item['desktop_app']=bool(desktop_name and (HOME/'Desktop'/(desktop_name+'.app')).is_dir())
        item['source']='Desktop app' if item['desktop_app'] else 'Local repository'
        item['ready']=item['installed']
        item['setup_issue']=''
        if spec['kind']=='cli':
            item['ready']=(repo/'.venv/bin'/item['id']).is_file()
            if not item['ready']:item['setup_issue']='The local command-line environment is missing. Installation is required before running this tool.'
        elif spec['kind']=='web':
            try:
                config=json.loads((HOME/'Desktop'/(spec['app']+'.app')/'Contents/Resources/launcher.json').read_text())
                item['ready']=item['installed'] and Path(config['command'][0]).is_file() and config.get('repo')==str(repo) and config.get('port')==spec['port']
                if not item['ready']:item['setup_issue']='The Desktop launcher or its runtime needs repair.'
            except (OSError,ValueError,KeyError,IndexError,TypeError):
                item['ready']=False;item['setup_issue']='The Desktop launcher configuration is unavailable.'
        if item.get('port'):
            with socket.socket() as probe:
                probe.settimeout(.15);item['running']=probe.connect_ex(('127.0.0.1',item['port']))==0
            item['url']='http://127.0.0.1:'+str(item['port'])+'/'
        rows.append(item)
    return dict(success=True,tools=rows)


def job_start(label,worker):
    with LOCK:
        if sum(j['status']=='running' for j in JOBS.values())>=3:raise ValueError('Three jobs are already running. Wait for one to finish.')
        job_id=uuid.uuid4().hex
        JOBS[job_id]=dict(id=job_id,label=label,status='running',started_at=time.time(),output='')
    def run():
        try:
            result=worker()
            with LOCK:JOBS[job_id].update(status='complete',**result)
        except Exception as exc:
            with LOCK:JOBS[job_id].update(status='failed',output=str(exc)[:2000])
    POOL.submit(run)
    return dict(success=True,job_id=job_id)


def run_tool(payload):
    key=payload.get('tool');spec=next((item for item in TOOLS if item['id']==key),None)
    if not spec:raise ValueError('Unknown tool')
    repo=REPOS/key
    if not repo.is_dir():raise ValueError('Repository is missing')
    if spec['kind']=='guide':
        return dict(success=True,guide=(repo/'README.md').read_text(errors='replace')[:80000])
    if spec['kind']=='web':
        resources=HOME/'Desktop'/(spec['app']+'.app')/'Contents/Resources'
        configs=list(resources.glob('*.json'))
        config=next((json.loads(p.read_text()) for p in configs if 'command' in json.loads(p.read_text())),None)
        if not config:raise ValueError('Desktop launcher configuration is missing')
        if config.get('repo')!=str(repo) or config.get('port')!=spec['port']:raise ValueError('Launcher does not match registered tool')
        def launch():
            with socket.socket() as probe:
                probe.settimeout(.3)
                occupied=probe.connect_ex(('127.0.0.1',spec['port']))==0
            if not occupied:
                environment=dict(os.environ);environment.update(config.get('env',{}))
                environment['PATH']=config.get('bin_dir','')+':'+environment.get('PATH','')
                (ROOT/'logs').mkdir(exist_ok=True)
                with (ROOT/'logs'/(key+'.log')).open('ab') as log:
                    proc=subprocess.Popen(config['command'],cwd=repo,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
                for _ in range(50):
                    if proc.poll() is not None:raise RuntimeError('Tool exited during startup. See logs/'+key+'.log')
                    try:
                        with urllib.request.urlopen(config['health_url'],timeout=1) as response:
                            content=response.read(200000).decode('utf-8','replace')
                        if config.get('signature','') in content:return dict(output='Local tool is ready.',url=config['url'])
                    except Exception:pass
                    time.sleep(.4)
                raise RuntimeError('Tool is still starting. Check its local log.')
            with urllib.request.urlopen(config['health_url'],timeout=2) as response:content=response.read(200000).decode('utf-8','replace')
            if config.get('signature','') not in content:raise RuntimeError('Port is occupied by a different service')
            return dict(output='Local tool is ready.',url=config['url'])
        return job_start(spec['name'],launch)
    target=str(payload.get('target','')).strip()
    if key=='holehe':
        if not re.fullmatch(r'[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,30}',target):raise ValueError('Enter a valid email address')
        cmd=[str(repo/'.venv/bin/holehe'),target,'--no-color']
    else:
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',target) or target.startswith('-'):raise ValueError('Enter a username using letters, numbers, dots or underscores')
        cmd=[str(repo/'.venv/bin/sherlock'),target,'--timeout','8','--print-found']
    def execute():
        output_dir=ROOT/'data'/'tool-runs'/uuid.uuid4().hex
        output_dir.mkdir(parents=True,mode=0o700)
        result=subprocess.run(cmd,cwd=output_dir,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
        if result.returncode:raise RuntimeError(result.stdout[-5000:] or 'Tool failed')
        output=re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',result.stdout)[-40000:]
        try:
            case_id=osint_casebook.record_lookup(key,target,output)
            if case_id:output+='\n\n[U1 casebook] Saved under research target '+target+'. Identity remains unverified.'
            return dict(output=output,case_id=case_id)
        except Exception:
            return dict(output=output+'\n\n[U1 casebook] Lookup finished, but saving failed. Import this result manually.',case_id=None)
    return job_start(spec['name'],execute)


def run_ai(payload):
    # Keep old clients fail-closed. Never translate a legacy payload into consent
    # for a different pipeline, or retain an unmanaged provider execution path.
    raise ValueError('Legacy AI execution is retired. Open AI Command, review your prompt, selected context and conversation history, then explicitly confirm a native managed request. No provider request was started.')


def handle_get(path,query):
    if path=='weather':return weather(query.get('city',['Melbourne'])[0])
    if path=='sports':return sports(query.get('sport',['afl'])[0])
    if path=='usage':return usage()
    if path=='tools':return tools_status()
    if path=='jobs':
        with LOCK:return dict(success=True,jobs=list(JOBS.values())[-30:])
    if path=='providers':return dict(success=True,providers=[dict(id='claude',name='Claude',mode='Local Claude Code session',ready=(HOME/'.local/bin/claude').exists(),url='https://claude.ai/'),dict(id='codex',name='Codex',mode='Local Codex session',ready=(HOME/'.local/bin/codex').exists(),url='https://chatgpt.com/codex'),dict(id='antigravity',name='Antigravity',mode='Prompt handoff to app',ready=(HOME/'.gemini/antigravity-ide').exists(),url='https://antigravity.google/'),dict(id='canva',name='Canva',mode='Design brief handoff',ready=False,url='https://www.canva.com/')])
    raise ValueError('Unknown workspace endpoint')


def handle_post(path,payload):
    if path=='tool':return run_tool(payload)
    if path=='ai':return run_ai(payload)
    if path=='casebook':return osint_casebook.action(payload)
    if path=='improvement':return improvement_agent.configure(payload)
    raise ValueError('Unknown workspace action')

NOTIFICATIONS=[]
NOTIFICATION_MARKS={}
NOTIFICATION_FILE=ROOT/'data'/'usage-thresholds.json'
MONITOR_STARTED=False


def observe_thresholds(snapshot):
    """Emit once for each crossed ten-percent threshold in each allowance window."""
    emitted=[]
    provider=snapshot.get('providers',{}).get('codex',{})
    if not provider.get('success') or provider.get('stale'):return emitted
    with LOCK:
        for window in provider.get('windows',[]):
            value=window.get('used_percent')
            if not isinstance(value,(int,float)) or not 0<=value<=100:continue
            key='codex:'+str(window.get('name'))+':'+str(window.get('period'))+':'+str(window.get('resets_at'))
            bucket=int(value//10)*10
            previous=NOTIFICATION_MARKS.get(key)
            if previous is None:NOTIFICATION_MARKS[key]=bucket;continue
            if bucket<=previous:continue
            for threshold in range(previous+10,bucket+1,10):
                item=dict(id=uuid.uuid4().hex,provider='Codex',title=str(window['name'])+' usage: '+str(threshold)+'%',message=str(threshold)+'% of this allowance window has been used.',threshold=threshold,resets_at=window.get('resets_at'),created_at=time.time())
                NOTIFICATIONS.append(item);emitted.append(item)
            NOTIFICATION_MARKS[key]=bucket
        del NOTIFICATIONS[:-100]
        if len(NOTIFICATION_MARKS)>100:
            for key in list(NOTIFICATION_MARKS)[:-60]:del NOTIFICATION_MARKS[key]
        NOTIFICATION_FILE.parent.mkdir(exist_ok=True)
        from utils.integrations_hub import persist
        persist(dict(marks=NOTIFICATION_MARKS,notifications=NOTIFICATIONS),str(NOTIFICATION_FILE))
    return emitted


def start_monitor():
    global MONITOR_STARTED
    with LOCK:
        if MONITOR_STARTED:return
        MONITOR_STARTED=True
        try:
            saved=json.loads(NOTIFICATION_FILE.read_text());NOTIFICATION_MARKS.update(saved.get('marks',{}));NOTIFICATIONS.extend(saved.get('notifications',[])[-100:])
        except (OSError,ValueError):pass
    def monitor():
        while True:
            try:observe_thresholds(usage())
            except Exception:pass
            time.sleep(60)
    threading.Thread(target=monitor,name='u1-usage-monitor',daemon=True).start()


_base_get=handle_get

def handle_get(path,query):
    start_monitor()
    if path.startswith('live/'):
        if path in {'live/news','live/stocks'}:
            return news_markets.handle_get(path.removeprefix('live/'),query)
        return live_bar.handle_get(path.removeprefix('live/'))
    if path=='casebook':return osint_casebook.listing(query)
    if path=='casebook/item':return osint_casebook.detail(query.get('id',[''])[0])
    if path=='improvement':return improvement_agent.snapshot()
    if path=='notifications':
        with LOCK:return dict(success=True,notifications=list(reversed(NOTIFICATIONS)),interval_seconds=60)
    return _base_get(path,query)


from utils import improvement_agent
improvement_agent.start(tools_status)

# PRISM extends the existing origin/CSRF-protected workspace API without
# replacing any legacy routes, jobs, account readers or research storage.
from utils import prism_workspace
from utils import u1_autopilot
from utils import u1_terminal
u1_autopilot.start()

_pre_prism_handle_get = handle_get
_pre_prism_handle_post = handle_post

def handle_get(path, query):
    if path in {"prism/autopilot", "/api/workspace/prism/autopilot"}:
        return u1_autopilot.snapshot()
    if path.startswith(("prism/", "/api/workspace/prism/")):
        return prism_workspace.handle_get(path, query)
    return _pre_prism_handle_get(path, query)

def handle_post(path, body):
    if path in {"terminal", "/api/workspace/terminal"}:
        return u1_terminal.handle_post(body)
    if path in {"prism/autopilot", "/api/workspace/prism/autopilot"}:
        return u1_autopilot.configure(body)
    if path.startswith(("prism/", "/api/workspace/prism/")):
        return prism_workspace.handle_post(path, body)
    return _pre_prism_handle_post(path, body)

# Evidence-first Agent Centre; preserve every existing workspace route.
from utils import u1_agent_centre
_u1_agents_previous_get = handle_get
_u1_agents_previous_post = handle_post

def handle_get(path, *args, **kwargs):
    if path in ('agents', '/api/workspace/agents'):
        return u1_agent_centre.snapshot()
    return _u1_agents_previous_get(path, *args, **kwargs)

def handle_post(path, payload, *args, **kwargs):
    if path in ('agents', '/api/workspace/agents'):
        return u1_agent_centre.handle_post(payload)
    return _u1_agents_previous_post(path, payload, *args, **kwargs)

u1_agent_centre.start()

# Local document drafts and an operator-entered ledger. No provider execution.
from utils import u1_business
_u1_business_previous_get = handle_get
_u1_business_previous_post = handle_post

def handle_get(path, *args, **kwargs):
    if path in ('business', '/api/workspace/business'):
        return u1_business.snapshot()
    return _u1_business_previous_get(path, *args, **kwargs)

def handle_post(path, payload, *args, **kwargs):
    if path in ('business', '/api/workspace/business'):
        return u1_business.action(payload)
    return _u1_business_previous_post(path, payload, *args, **kwargs)

from utils import u1_google, u1_recovery
_u1_reliability_previous_get = handle_get
_u1_reliability_previous_post = handle_post

def handle_get(path, *args, **kwargs):
    if path == 'google':
        return u1_google.snapshot()
    if path == 'recovery':
        return u1_recovery.snapshot()
    return _u1_reliability_previous_get(path, *args, **kwargs)

def handle_post(path, payload, *args, **kwargs):
    if path == 'google':
        return u1_google.action(payload)
    if path == 'recovery':
        return u1_recovery.action(payload)
    return _u1_reliability_previous_post(path, payload, *args, **kwargs)

u1_google.start()
