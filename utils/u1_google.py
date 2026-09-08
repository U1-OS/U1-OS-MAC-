"""Read-only Google OAuth, bounded sync and review-before-local-calendar changes."""
import base64
import hashlib
import json
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo
from utils import prism_workspace as workspace
from utils import u1_business

ROOT=Path(__file__).resolve().parents[1]
SCOPES=['https://www.googleapis.com/auth/gmail.readonly','https://www.googleapis.com/auth/calendar.events.readonly']
KEY='u1_google_readonly_v1'
ACCOUNT=hashlib.sha256(str(ROOT).encode()).hexdigest()[:32]
LOCK=threading.RLock()
PENDING=None
JOB=None
GENERATION=0
SESSION_VERIFIED=False
STARTED=False
PAUSED=False


def _safety_blocked():
    """Never call while holding LOCK: Safety may notify cancel_all()."""
    try:
        from utils.u1_safety import manager
        return bool(manager().blocked())
    except Exception:
        return True


def _check_epoch(epoch):
    """Caller holds LOCK. This check performs no Safety or external operation."""
    if epoch!=GENERATION or PAUSED:
        raise ValueError('Google work was cancelled or paused. Unlock Safety and explicitly choose Sync now or Connect to resume.')


def _epoch(resume=False):
    global PAUSED
    with LOCK:epoch=GENERATION
    if _safety_blocked():raise ValueError('Safety is locked. No new Google operation was started.')
    with LOCK:
        if epoch!=GENERATION:raise ValueError('Google work was cancelled before dispatch.')
        if resume:PAUSED=False
        _check_epoch(epoch)
        return epoch


def _allowed(epoch):
    blocked=_safety_blocked()
    with LOCK:
        if blocked:raise ValueError('Safety blocked this Google operation.')
        _check_epoch(epoch)


def _request(epoch,*args,**kwargs):
    _allowed(epoch)
    with LOCK:_check_epoch(epoch)
    result=request(*args,**kwargs)
    _allowed(epoch)
    return result


def paused():
    with LOCK:return PAUSED


def cancel_all():
    """Safety hook, called outside its mutex. No DB, Keychain, network or startup."""
    global GENERATION,PENDING,PAUSED,SESSION_VERIFIED
    with LOCK:
        GENERATION+=1;PAUSED=True;SESSION_VERIFIED=False
        flow=PENDING;PENDING=None
        if flow:
            flow['status']='cancelled'
            if flow.get('stop'):flow['stop'].set()
        if JOB and JOB['status']=='running':
            JOB.update(status='cancelling',message='Google cancellation requested; any in-flight read must finish before its result is discarded.')
        return {'success':True,'paused':True,'generation':GENERATION,'oauth_pending':False,
                'job':dict(JOB) if JOB else None}


def stored():
    with workspace.database() as connection:
        row=connection.execute('SELECT value FROM preferences WHERE key=?',(KEY,)).fetchone()
    value=json.loads(row[0]) if row else {}
    return {'configured':False,'auto_sync':False,'include_pdfs':False,'messages':[],'events':[],'bindings':{},**value}


def save(value):
    with workspace.database() as connection:
        connection.execute('INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)',(KEY,json.dumps(value)))


def keychain(operation,value=None):
    helper=ROOT/'.runtime'/'u1-keychain'
    if not helper.is_file():raise ValueError('Build the local Keychain helper before configuring Google Connect.')
    try:
        result=subprocess.run([str(helper),operation,ACCOUNT],input=json.dumps(value).encode() if value is not None else b'',stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=35,check=False)
        if result.returncode:raise ValueError('Keychain unavailable or access denied. No plaintext fallback was used.')
        return json.loads(result.stdout)
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError):
        raise ValueError('The local Keychain operation did not complete.') from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def request(url,form=None,token=None,raw=False):
    parts=urllib.parse.urlsplit(url)
    if parts.scheme!='https' or parts.hostname not in {'oauth2.googleapis.com','gmail.googleapis.com','www.googleapis.com'} or parts.username or parts.password:
        raise ValueError('Unsupported Google API destination.')
    headers={'User-Agent':'U1OS/read-only-personal-workspace','Accept':'application/json'}
    data=None
    if form is not None:
        data=urllib.parse.urlencode(form).encode();headers['Content-Type']='application/x-www-form-urlencoded'
    if token:headers['Authorization']='Bearer '+token
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(urllib.request.Request(url,data=data,headers=headers),timeout=12) as response:
            content=response.read(8*1024*1024+1)
        if len(content)>8*1024*1024:raise ValueError('The provider response exceeded the sync size limit.')
        return content if raw else json.loads(content)
    except urllib.error.HTTPError as error:
        raise ValueError('Google request declined (HTTP '+str(error.code)+'). Review the account permissions or reconnect.') from None
    except (urllib.error.URLError,json.JSONDecodeError,TimeoutError):
        raise ValueError('Google is unavailable. Previously stored information is not a live response.') from None


def snapshot():
    with LOCK:
        value=stored()
        pending=PENDING
        return {'success':True,**value,'paused':PAUSED,'keychain_helper':(ROOT/'.runtime/u1-keychain').is_file(),'session_verified':SESSION_VERIFIED,
                'stale':not SESSION_VERIFIED or time.time()-value.get('last_sync',0)>660,
                'oauth_status':pending['status'] if pending else 'idle','job':dict(JOB) if JOB else None,'scopes':SCOPES,
                'notice':'Google access is read-only. Local drafts, extracted text and imported PDFs are unencrypted workspace data. No email, calendar or AI-provider write is performed.'}


def configure(body):
    global GENERATION, PENDING, SESSION_VERIFIED
    data=body.get('client')
    if not isinstance(data,dict) or not isinstance(data.get('installed'),dict):
        raise ValueError('Choose a Google Desktop app OAuth JSON file, not a web-server credential.')
    client=data['installed']
    client_id=client.get('client_id','')
    secret=client.get('client_secret','')
    if not isinstance(client_id,str) or not client_id.endswith('.apps.googleusercontent.com') or len(client_id)>300 or not isinstance(secret,str) or len(secret)>8192:
        raise ValueError('The desktop OAuth client fields are invalid.')
    epoch=_epoch(resume=True)
    with LOCK:
        _check_epoch(epoch)
        if JOB and JOB['status'] in {'running','cancelling'}:raise ValueError('Wait for the current sync before replacing the client.')
        if PENDING and PENDING['status'] in {'authorising','exchanging'} and time.time()<PENDING['expires']:
            raise ValueError('Finish or disconnect the pending Google sign-in before replacing the client.')
        keychain('set',{'client_id':client_id,'client_secret':secret})
        GENERATION+=1;PENDING=None;SESSION_VERIFIED=False
        value=stored();value.update(configured=True,auto_sync=False,account=None,last_sync=0,messages=[],events=[],bindings={})
        save(value)
    return {'success':True,'message':'Desktop client saved in Keychain. Google account access has not been granted.'}


def begin():
    global PENDING
    epoch=_epoch(resume=True)
    with LOCK:
        _check_epoch(epoch)
        if JOB and JOB['status'] in {'running','cancelling'}:raise ValueError('Finish or cancel the current Google sync before connecting.')
        if PENDING and PENDING['status'] in {'authorising','exchanging'} and time.time()<PENDING['expires']:
            return {'success':True,'authorization_url':PENDING['url'],'expires':PENDING['expires']}
        credentials=keychain('get')
    _allowed(epoch)
    verifier=secrets.token_urlsafe(64)
    flow={'state':secrets.token_urlsafe(32),'verifier':verifier,'expires':time.time()+600,
          'status':'authorising','generation':epoch,'stop':threading.Event()}
    class Callback(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(2)
        def log_message(self,*args):pass
        def do_GET(self):
            global SESSION_VERIFIED
            completed=False
            message='The authorisation could not be verified. Return to U1 OS and reconnect.'
            try:
                if len(self.path)>=8192:raise ValueError('Invalid callback')
                parsed=urllib.parse.urlsplit(self.path)
                values=urllib.parse.parse_qs(parsed.query,max_num_fields=8)
                states=values.get('state',[])
                if (parsed.path!='/oauth2callback' or self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}'
                        or len(states)!=1 or not re.fullmatch(r'[A-Za-z0-9_-]{43}',states[0])
                        or not secrets.compare_digest(states[0],flow['state'])):raise ValueError('Invalid callback')
                _allowed(epoch)
                with LOCK:
                    _check_epoch(epoch)
                    if PENDING is not flow or flow['status']!='authorising' or time.time()>=flow['expires']:raise ValueError('Expired callback')
                    flow['status']='exchanging'
                code=values.get('code',[])
                if len(code)!=1 or not 1<=len(code[0])<=4096 or values.get('error'):raise ValueError('Consent not completed')
                token=_request(epoch,'https://oauth2.googleapis.com/token',{'client_id':credentials['client_id'],'client_secret':credentials.get('client_secret',''),'code':code[0],'code_verifier':flow['verifier'],'redirect_uri':flow['redirect'],'grant_type':'authorization_code'})
                if not token.get('refresh_token'):raise ValueError('Offline access not granted')
                _allowed(epoch)
                with LOCK:
                    _check_epoch(epoch)
                    if PENDING is not flow or flow['status']!='exchanging' or time.time()>=flow['expires']:raise ValueError('Expired callback')
                    keychain('set',{**credentials,'refresh_token':token['refresh_token'],'scopes':token.get('scope','')})
                    flow['status']='authorised';SESSION_VERIFIED=False;completed=True
                message='Authorisation saved in Mac Keychain. Return to U1 OS and choose Sync now to verify access.'
            except Exception:
                with LOCK:
                    if PENDING is flow and flow['status']=='exchanging':flow['status']='needs_attention'
            finally:
                with LOCK:
                    if flow['status']!='authorising':flow['stop'].set()
            self.send_response(200 if completed else 400)
            self.send_header('Content-Type','text/plain; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('Connection','close');self.end_headers()
            self.wfile.write(message.encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Callback)
    server.timeout=0.5
    server.handle_error=lambda *args:None
    flow['redirect']=f'http://127.0.0.1:{server.server_port}/oauth2callback'
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    flow['url']='https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode({'client_id':credentials['client_id'],'redirect_uri':flow['redirect'],'response_type':'code','scope':' '.join(SCOPES),'state':flow['state'],'code_challenge':challenge,'code_challenge_method':'S256','access_type':'offline','prompt':'consent'})
    try:
        _allowed(epoch)
        with LOCK:
            _check_epoch(epoch)
            PENDING=flow
        def listen():
            try:
                while not flow['stop'].is_set() and time.time()<flow['expires']:server.handle_request()
            finally:
                server.server_close()
                with LOCK:
                    if flow['status'] in {'authorising','exchanging'}:flow['status']='expired'
        threading.Thread(target=listen,name='u1-google-oauth',daemon=True).start()
        _allowed(epoch)
        with LOCK:
            _check_epoch(epoch)
            return {'success':True,'authorization_url':flow['url'],'expires':flow['expires']}
    except Exception:
        flow['stop'].set();server.server_close()
        with LOCK:
            if PENDING is flow:PENDING=None
        raise


def decode_body(payload):
    texts=[];attachments=[]
    def walk(part,depth=0):
        if depth>10:return
        body=part.get('body') or {}
        if part.get('mimeType')=='text/plain' and body.get('data'):
            raw=str(body['data'])[:64000]
            try:texts.append(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)).decode('utf-8','replace')[:12000])
            except (ValueError,TypeError):pass
        if part.get('mimeType')=='application/pdf' and body.get('attachmentId'):
            attachments.append({'id':str(body['attachmentId'])[:1000],'name':str(part.get('filename') or 'attachment.pdf')[:180],'size':body.get('size',0)})
        for child in (part.get('parts') or [])[:50]:walk(child,depth+1)
    walk(payload)
    return '\n'.join(texts)[:12000],attachments[:5]


def extract_pdf(raw):
    try:
        result=subprocess.run([sys.executable,str(ROOT/'utils/u1_pdf_extract.py')],input=raw,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=12,check=False)
        return json.loads(result.stdout) if result.returncode==0 else {'success':False,'notice':'PDF extraction reached its resource limit.'}
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError):return {'success':False,'notice':'PDF extraction unavailable; review the original.'}


def import_pdf(raw,name):
    if len(raw)>5*1024*1024 or not raw.startswith(b'%PDF-'):raise ValueError('PDF import exceeded the supported limit.')
    checksum=hashlib.sha256(raw).hexdigest()
    existing=next((f for f in workspace.files() if f.get('checksum')==checksum and f['status']=='ready'),None)
    if existing:return existing['id']
    name=name.replace('\\','/').rsplit('/',1)[-1] or 'attachment.pdf'
    started=workspace.handle_post('prism/upload-start',{'name':name,'size':len(raw),'mime':'application/pdf','folder':'Gmail PDFs'})
    for offset in range(0,len(raw),32768):
        workspace.handle_post('prism/upload-chunk',{'id':started['id'],'offset':offset,'content':base64.b64encode(raw[offset:offset+32768]).decode()})
    return started['id']


def sync(*,resume=True):
    global JOB,SESSION_VERIFIED
    epoch=_epoch(resume=resume)
    with LOCK:
        _check_epoch(epoch)
        if JOB and JOB['status'] in {'running','cancelling'}:return {'success':True,'job_id':JOB['id'],'already_running':True}
        if PENDING and PENDING['status'] in {'authorising','exchanging'}:raise ValueError('Complete or cancel Google authorisation before syncing.')
        JOB={'id':uuid.uuid4().hex,'status':'running','started':time.time(),'message':'Verifying read-only Google access...'}
        job=JOB
    def run():
        global SESSION_VERIFIED
        try:
            _allowed(epoch)
            with LOCK:
                _check_epoch(epoch)
                credentials=keychain('get')
            if not credentials.get('refresh_token'):raise ValueError('Authorise Google before syncing.')
            token=_request(epoch,'https://oauth2.googleapis.com/token',{'client_id':credentials['client_id'],'client_secret':credentials.get('client_secret',''),'refresh_token':credentials['refresh_token'],'grant_type':'refresh_token'}).get('access_token')
            if not token:raise ValueError('Google did not return an access token.')
            profile=_request(epoch,'https://gmail.googleapis.com/gmail/v1/users/me/profile',token=token)
            messages=_request(epoch,'https://gmail.googleapis.com/gmail/v1/users/me/messages?'+urllib.parse.urlencode({'maxResults':20,'q':'newer_than:14d -in:spam -in:trash'}),token=token)
            config=stored();mail=[];pdf_budget=3;warnings=[]
            for reference in messages.get('messages',[])[:20]:
                with LOCK:
                    _check_epoch(epoch)
                message_id=str(reference.get('id',''))
                data=_request(epoch,'https://gmail.googleapis.com/gmail/v1/users/me/messages/'+urllib.parse.quote(message_id,safe='')+'?format=full',token=token)
                headers={h.get('name','').lower():h.get('value','') for h in data.get('payload',{}).get('headers',[])}
                text,attachments=decode_body(data.get('payload',{}))
                row={'id':message_id,'title':str(headers.get('subject') or 'Untitled message')[:160],'from':str(headers.get('from',''))[:250],'date':str(headers.get('date',''))[:120],'text':text or str(data.get('snippet',''))[:12000],'attachments':attachments,'url':'https://mail.google.com/mail/u/0/#all/'+urllib.parse.quote(message_id,safe='')}
                if config.get('include_pdfs'):
                    for attachment in attachments:
                        if pdf_budget<=0 or not isinstance(attachment['size'],int) or not 0<attachment['size']<=5*1024*1024:continue
                        pdf_budget-=1
                        part=_request(epoch,'https://gmail.googleapis.com/gmail/v1/users/me/messages/'+urllib.parse.quote(message_id,safe='')+'/attachments/'+urllib.parse.quote(attachment['id'],safe=''),token=token)
                        encoded=part.get('data','');raw=base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4))
                        extracted=extract_pdf(raw)
                        with LOCK:
                            _check_epoch(epoch)
                            attachment['local_file_id']=import_pdf(raw,attachment['name'])
                        attachment['extraction_notice']=extracted.get('notice','')
                        if extracted.get('text'):row['text']=(row['text']+'\nPDF '+attachment['name']+':\n'+extracted['text'])[:12000]
                mail.append(row)
            now=datetime.now(timezone.utc)
            query=urllib.parse.urlencode({'timeMin':(now-timedelta(days=7)).isoformat(),'timeMax':(now+timedelta(days=90)).isoformat(),'singleEvents':'true','showDeleted':'true','maxResults':100})
            calendar=_request(epoch,'https://www.googleapis.com/calendar/v3/calendars/primary/events?'+query,token=token)
            events=[]
            for event in calendar.get('items',[])[:100]:
                start=event.get('start') or {};end=event.get('end') or {}
                events.append({'id':str(event.get('id',''))[:300],'version':str(event.get('etag',''))[:300],'title':str(event.get('summary') or 'Calendar event')[:160],
                               'status':event.get('status','confirmed'),'start':start.get('dateTime') or start.get('date',''),'end':end.get('dateTime') or end.get('date',''),
                               'location':str(event.get('location',''))[:200],'notes':str(event.get('description',''))[:7500],'url':str(event.get('htmlLink',''))[:1200]})
            _allowed(epoch)
            with LOCK:
                _check_epoch(epoch)
                value=stored()
                for row in mail:
                    if re.search(r'appoint|meeting|booking|deadline|invoice|schedule|due date',row['title']+' '+row['text'],re.I):
                        try:u1_business.import_source('gmail:'+row['id'],row['title'],row['text'],row['url'])
                        except ValueError:warnings.append('A source could not enter the review queue; review the inbox directly.')
                value.update(messages=mail,events=events,account=profile.get('emailAddress'),last_sync=time.time(),warnings=warnings,
                             calendar_limited=bool(calendar.get('nextPageToken')),mail_limited=bool(messages.get('nextPageToken')),
                             coverage='Latest 20 messages from 14 days; first 100 primary-calendar events from 7 days ago to 90 days ahead. Missing events are never treated as cancellations.')
                save(value);SESSION_VERIFIED=True;job.update(status='complete',finished=time.time(),message='Read-only sync completed; proposed actions still require review.')
        except Exception as error:
            with LOCK:
                cancelled=epoch!=GENERATION or PAUSED
                if epoch==GENERATION:SESSION_VERIFIED=False
                job.update(status='cancelled' if cancelled else 'failed',finished=time.time(),message='Google work was cancelled; late results were discarded.' if cancelled else str(error) if isinstance(error,ValueError) else 'Sync failed. Previously stored data was retained and is not a live result.')
    threading.Thread(target=run,name='u1-google-sync',daemon=True).start()
    return {'success':True,'job_id':job['id']}


def approve_event(body):
    with LOCK:
        value=stored();event=next((e for e in value['events'] if e['id']==body.get('id')),None)
        if body.get('confirmed') is not True or not event or event['version']!=body.get('version'):
            raise ValueError('Reload, review and confirm the current provider event.')
        binding=value['bindings'].get(event['id'])
        if binding and binding['version']==event['version']:return {'success':True,'message':'This provider version has already been reviewed.'}
        if event['status']=='cancelled':
            if binding:
                with workspace.database() as connection:
                    result=connection.execute('UPDATE records SET deleted=? WHERE id=? AND kind=? AND updated=? AND deleted IS NULL',(time.time(),binding['record_id'],'event',binding['updated']))
                    if result.rowcount!=1:raise ValueError('The local event changed or was removed. Review it in Calendar; it was not overwritten.')
                binding['version']=event['version'];save(value)
            return {'success':True,'message':'Provider cancellation reviewed. Any matching unchanged local event was moved to Trash.'}
        if not event['start']:raise ValueError('The provider did not supply a usable start time.')
        record={'id':binding['record_id'] if binding else uuid.uuid4().hex,'kind':'event','title':event['title'],
                'payload':{'start':event['start'],'end':event['end'],'location':event['location'],'notes':('Google Calendar source: '+event['url']+'\n'+event['notes'])[:8000]}}
        if binding:
            current=next((row for row in workspace.records() if row['id']==binding['record_id']),None)
            if not current:raise ValueError('The previously imported local event was removed. It will not be recreated automatically.')
            record['expected_updated']=binding['updated']
        result=workspace.handle_post('prism/record',record)
        value['bindings'][event['id']]={'record_id':record['id'],'updated':result['updated'],'version':event['version']}
        save(value)
        return {'success':True,'message':'Confirmed provider event saved to the local calendar. Google was not modified.'}


def action(body):
    global GENERATION,PENDING,SESSION_VERIFIED
    operation=body.get('action')
    if operation=='configure':return configure(body)
    if operation=='connect':return begin()
    if operation=='sync':return sync()
    if operation=='approve_event':return approve_event(body)
    if operation=='settings':
        with LOCK:
            value=stored()
            for field in ('auto_sync','include_pdfs'):
                if type(body.get(field)) is not bool:raise ValueError('Sync preferences must be true or false.')
                value[field]=body[field]
            save(value)
        return {'success':True,'message':'Read-only sync preferences saved. Automatic sync runs only while the local server runs.'}
    if operation=='disconnect':
        cancel_all()
        with LOCK:
            value=stored();value.update(auto_sync=False,configured=False);save(value)
            try:
                credentials=keychain('get')
                revoked=False
                if credentials.get('refresh_token'):
                    request('https://oauth2.googleapis.com/revoke',{'token':credentials['refresh_token']},raw=True)
                    revoked=True
            except ValueError:revoked=False
            keychain('delete')
        return {'success':True,'message':'Local connection removed. '+('Google grant revocation confirmed.' if revoked else 'Provider revocation was not confirmed; review Google Account permissions.')+' Existing imported data was retained.'}
    raise ValueError('Choose a supported Google connection action.')


def start():
    global STARTED
    with LOCK:
        if STARTED:return
        STARTED=True
    def loop():
        while True:
            try:
                if not _safety_blocked() and not paused():
                    value=stored()
                    if value.get('auto_sync') and value.get('configured') and time.time()-value.get('last_sync',0)>300 and (not JOB or time.time()-JOB['started']>300):sync(resume=False)
            except Exception:pass
            time.sleep(60)
    threading.Thread(target=loop,name='u1-google-autosync',daemon=True).start()
