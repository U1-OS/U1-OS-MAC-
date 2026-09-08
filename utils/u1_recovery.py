"""Managed-workspace backups and verified isolated restores, never active overwrite."""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path
from utils import prism_workspace as workspace

ROOT = Path(__file__).resolve().parents[1] / 'data' / 'recovery'
LOCK = threading.RLock()
JOBS = {}
LIMIT = workspace.MAX_STORAGE + 64*1024*1024
IDENTIFIER = re.compile(r'^[a-f0-9]{32}$')


def directories():
    for directory in (ROOT, ROOT/'backups', ROOT/'restores'):
        if directory.is_symlink():
            raise ValueError('Recovery storage must not be a symbolic link.')
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        directory.chmod(0o700)


def digest_file(path):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Backup input must be an ordinary file.')
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = stream.read(1024*1024)
            if not chunk:
                return digest.hexdigest(), size
            size += len(chunk)
            if size > LIMIT:
                raise ValueError('The backup input exceeds the size limit.')
            digest.update(chunk)


def make_backup():
    directories()
    identifier = uuid.uuid4().hex
    target = ROOT/'backups'/(identifier+'.zip')
    with tempfile.TemporaryDirectory(prefix='.building-', dir=ROOT) as temporary:
        directory = Path(temporary)
        db_copy = directory/'workspace.sqlite3'
        # The workspace lock covers the DB snapshot and file copy. An active
        # multipart import is rejected rather than archived half-complete.
        with workspace.database() as connection:
            if connection.execute("SELECT COUNT(*) FROM files WHERE status='uploading' AND deleted IS NULL").fetchone()[0]:
                raise ValueError('Finish pending file imports before creating a backup.')
            with sqlite3.connect(db_copy) as backup:
                connection.backup(backup)
            db_copy.chmod(0o600)
            rows = connection.execute("SELECT id,size,checksum FROM files WHERE status='ready'").fetchall()
            if sum(row['size'] for row in rows) > workspace.MAX_STORAGE:
                raise ValueError('Managed file storage exceeds the supported backup size.')
            manifest = {'format':'u1-managed-workspace','version':1,'created':time.time(),'files':{},
                        'coverage':['Managed records, local preferences and business data','Imported file contents, including managed Trash'],
                        'excluded':['Provider credentials','Other plugin databases','Source code and native app binaries'],
                        'encrypted':False}
            archive_path = directory/'archive.zip'
            with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as archive:
                for source, name, expected in [(db_copy, 'workspace.sqlite3', None)] + [(workspace.DATA/'files'/row['id'], 'files/'+row['id'], row['checksum']) for row in rows]:
                    digest=hashlib.sha256();size=0
                    flags=os.O_RDONLY | getattr(os,'O_NOFOLLOW',0)
                    with os.fdopen(os.open(source,flags),'rb') as input_file, archive.open(name,'w') as output_file:
                        if not stat.S_ISREG(os.fstat(input_file.fileno()).st_mode):
                            raise ValueError('Backup input must be an ordinary file.')
                        while True:
                            chunk=input_file.read(1024*1024)
                            if not chunk:break
                            size+=len(chunk)
                            if size>LIMIT:raise ValueError('The backup input exceeds the size limit.')
                            digest.update(chunk);output_file.write(chunk)
                    checksum=digest.hexdigest()
                    if expected and checksum != expected:
                        raise ValueError('An imported file failed its stored checksum. No backup was published.')
                    manifest['files'][name] = {'sha256':checksum,'size':size}
                archive.writestr('manifest.json', json.dumps(manifest))
            archive_path.chmod(0o600)
            os.replace(archive_path, target)
    return {'backup_id':identifier,'size':target.stat().st_size,'managed_files':len(rows),'created':manifest['created']}


def restore_backup(identifier):
    if not isinstance(identifier,str) or not IDENTIFIER.fullmatch(identifier):
        raise ValueError('Choose a local backup identifier.')
    directories()
    archive_path = ROOT/'backups'/(identifier+'.zip')
    if archive_path.is_symlink() or not archive_path.is_file() or archive_path.stat().st_size > LIMIT:
        raise ValueError('That local backup is unavailable or too large.')
    restore_id = uuid.uuid4().hex
    destination = ROOT/'restores'/restore_id
    with tempfile.TemporaryDirectory(prefix='.restoring-', dir=ROOT) as temporary:
        stage = Path(temporary)/'prism'
        stage.mkdir(mode=0o700)
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members)>2000 or len({m.filename for m in members}) != len(members) or sum(m.file_size for m in members)>LIMIT:
                raise ValueError('Backup members exceed the supported limits.')
            if any(m.file_size<0 or stat.S_ISLNK(m.external_attr>>16) for m in members):
                raise ValueError('Symbolic links are not supported in backups.')
            manifest_info = archive.getinfo('manifest.json')
            if manifest_info.file_size>512*1024:
                raise ValueError('Backup manifest is too large.')
            manifest=json.loads(archive.read('manifest.json'))
            if manifest.get('format')!='u1-managed-workspace' or manifest.get('version')!=1:
                raise ValueError('Unsupported backup format.')
            files=manifest.get('files')
            if not isinstance(files,dict) or 'workspace.sqlite3' not in files or set(files)|{'manifest.json'} != {m.filename for m in members}:
                raise ValueError('The backup manifest does not match the archive.')
            for name, expected in files.items():
                if name!='workspace.sqlite3' and not re.fullmatch(r'files/[a-f0-9]{32}',name):
                    raise ValueError('Unsafe backup member path.')
                info=archive.getinfo(name)
                if not isinstance(expected,dict) or info.file_size!=expected.get('size'):
                    raise ValueError('The backup size manifest is invalid.')
                output=stage/name
                output.parent.mkdir(mode=0o700,exist_ok=True)
                total=0
                with archive.open(name) as source, open(output,'xb') as target:
                    os.chmod(output,0o600)
                    digest=hashlib.sha256()
                    while True:
                        chunk=source.read(1024*1024)
                        if not chunk:break
                        total+=len(chunk)
                        if total>info.file_size:raise ValueError('Backup output exceeded its declared size.')
                        digest.update(chunk);target.write(chunk)
                if total!=info.file_size or digest.hexdigest()!=expected.get('sha256'):
                    raise ValueError('Backup checksum verification failed.')
        with sqlite3.connect((stage/'workspace.sqlite3').as_uri()+'?mode=ro',uri=True) as connection:
            if connection.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise ValueError('The restored database failed its integrity check.')
            rows=connection.execute("SELECT id,size,checksum FROM files WHERE status='ready'").fetchall()
            for file_id,size,checksum in rows:
                expected=files.get('files/'+file_id)
                if not expected or expected['size']!=size or (checksum and expected['sha256']!=checksum):
                    raise ValueError('Restored file metadata does not match its contents.')
            record_count=connection.execute('SELECT COUNT(*) FROM records').fetchone()[0]
        os.replace(stage,destination)
    return {'restore_id':restore_id,'path':str(destination),'records':record_count,'files':len(rows),'active_workspace_changed':False}


def snapshot():
    directories()
    backups=[]
    for path in (ROOT/'backups').glob('*.zip'):
        if IDENTIFIER.fullmatch(path.stem) and not path.is_symlink() and path.is_file():
            backups.append({'id':path.stem,'created':path.stat().st_mtime,'size':path.stat().st_size})
    with LOCK:
        return {'success':True,'backups':sorted(backups,key=lambda row:row['created'],reverse=True)[:50],'jobs':list(JOBS.values())[-10:],
                'coverage':'Managed database and imported files, including Trash. Not credentials, other plugin stores or source code.',
                'notice':'Unencrypted owner-only local archives. Restores go to a separate directory and never overwrite the running workspace.'}


def action(body):
    if not isinstance(body,dict) or body.get('action') not in {'backup','restore'} or body.get('confirmed') is not True:
        raise ValueError('Review the backup scope and confirm the requested recovery action.')
    with LOCK:
        active=next((job for job in JOBS.values() if job['status']=='running'),None)
        if active:return {'success':True,'job_id':active['id'],'already_running':True}
        job={'id':uuid.uuid4().hex,'action':body['action'],'status':'running','started':time.time()}
        JOBS[job['id']]=job
        if len(JOBS)>20:del JOBS[next(iter(JOBS))]
    def run():
        try:
            result=make_backup() if body['action']=='backup' else restore_backup(body.get('id'))
            with LOCK:job.update(status='complete',result=result,finished=time.time())
        except Exception as error:
            message=str(error) if isinstance(error,ValueError) else 'Recovery failed; the active workspace was not replaced.'
            with LOCK:job.update(status='failed',error=message,finished=time.time())
    threading.Thread(target=run,name='u1-recovery',daemon=True).start()
    return {'success':True,'job_id':job['id']}
