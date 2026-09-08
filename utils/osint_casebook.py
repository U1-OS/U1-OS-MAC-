"""Local research targets and attributed observations, never verified identities by inference."""
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = ROOT / 'data' / 'casebook'
DATABASE = DIRECTORY / 'research.sqlite3'
LOCK = threading.RLock()


@contextmanager
def connect():
    DIRECTORY.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(DIRECTORY, 0o700)
    db = sqlite3.connect(DATABASE, timeout=10)
    try:
        os.chmod(DATABASE, 0o600)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA secure_delete=ON')
        db.executescript('''
      CREATE TABLE IF NOT EXISTS subjects (
        id TEXT PRIMARY KEY, target TEXT NOT NULL, kind TEXT NOT NULL,
        name TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', photo TEXT NOT NULL DEFAULT '',
        photo_source TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL,
        UNIQUE(target, kind));
      CREATE TABLE IF NOT EXISTS observations (
        id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        tool TEXT NOT NULL, output TEXT NOT NULL, sources TEXT NOT NULL, created_at REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        with db:
            yield db
    finally:
        db.close()


def text(value, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError('Invalid text or text exceeds the allowed length')
    return value.strip()


def url(value):
    value = text(value, 2000)
    if not value:
        return ''
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Source links must be HTTP or HTTPS without credentials')
    return value


def enabled(db):
    row = db.execute("SELECT value FROM preferences WHERE key='autosave'").fetchone()
    return not row or row['value'] != 'false'


def upsert(db, target, kind):
    now = time.time()
    case_id = uuid.uuid4().hex
    db.execute('INSERT OR IGNORE INTO subjects(id,target,kind,name,created_at,updated_at) VALUES(?,?,?,?,?,?)',
               (case_id, target, kind, target, now, now))
    row = db.execute('SELECT id FROM subjects WHERE target=? AND kind=?', (target, kind)).fetchone()
    return row['id']


def record_lookup(tool, target, output):
    with LOCK, connect() as db:
        if not enabled(db):
            return None
        kind = 'email' if tool == 'holehe' else 'username'
        case_id = upsert(db, text(target, 254), kind)
        add_observation(db, case_id, tool, output[:40000], '')
        return case_id


def add_observation(db, case_id, tool, output, source):
    sources = []
    if source:
        sources.append(url(source))
    for match in re.findall(r'https?://[^\s<>"\x1b]+', output):
        try:
            candidate = url(match.rstrip(').,;]'))
            if candidate not in sources:
                sources.append(candidate)
        except ValueError:
            continue
        if len(sources) >= 80:
            break
    now = time.time()
    db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)',
               (uuid.uuid4().hex, case_id, text(tool, 80), text(output, 40000), json.dumps(sources), now))
    db.execute('UPDATE subjects SET updated_at=? WHERE id=?', (now, case_id))


def listing(query):
    search = text(query.get('q', [''])[0], 150)
    offset = max(0, min(100000, int(query.get('offset', ['0'])[0])))
    with LOCK, connect() as db:
        rows = db.execute('''SELECT s.id,s.name,s.target,s.kind,s.updated_at,
            (s.photo!='') AS has_photo,COUNT(o.id) AS observations FROM subjects s
            LEFT JOIN observations o ON o.subject_id=s.id
            WHERE instr(lower(s.name||' '||s.target),lower(?))>0
            GROUP BY s.id ORDER BY s.updated_at DESC LIMIT 50 OFFSET ?''', (search, offset)).fetchall()
        total = db.execute('SELECT COUNT(*) FROM subjects WHERE instr(lower(name||\' \'||target),lower(?))>0', (search,)).fetchone()[0]
        return dict(success=True, cases=[dict(row) for row in rows], total=total, offset=offset,
                    autosave=enabled(db), notice='Research targets, not confirmed identities. Stored locally without encryption; excluded from Git by the data/ ignore rule.')


def detail(case_id):
    with LOCK, connect() as db:
        row = db.execute('SELECT * FROM subjects WHERE id=?', (case_id,)).fetchone()
        if not row:
            raise ValueError('Case not found')
        item = dict(row)
        item['observations'] = []
        for observation in db.execute('SELECT * FROM observations WHERE subject_id=? ORDER BY created_at DESC', (case_id,)):
            value = dict(observation)
            value['sources'] = json.loads(value['sources'])
            item['observations'].append(value)
        item['identity_status'] = 'Unverified research target; matching handles do not establish identity.'
        return dict(success=True, case=item)


def action(payload):
    action_name = payload.get('action')
    if action_name == 'tiktok_import':
        return import_tiktok(payload.get('url', ''))
    with LOCK, connect() as db:
        if action_name == 'autosave':
            if not isinstance(payload.get('enabled'), bool):
                raise ValueError('Expected an enabled boolean')
            db.execute("INSERT OR REPLACE INTO preferences VALUES('autosave',?)", ('true' if payload['enabled'] else 'false',))
            return dict(success=True)
        if action_name == 'create':
            target = text(payload.get('target', ''), 254)
            kind = payload.get('kind', 'research')
            if not target or kind not in {'username', 'email', 'research'}:
                raise ValueError('Enter a research target and a supported target type')
            return dict(success=True, case_id=upsert(db, target, kind))
        case_id = text(payload.get('id', ''), 32)
        if not db.execute('SELECT id FROM subjects WHERE id=?', (case_id,)).fetchone():
            raise ValueError('Case not found')
        if action_name == 'delete':
            db.execute('DELETE FROM subjects WHERE id=?', (case_id,))
        elif action_name == 'update':
            name = text(payload.get('name', ''), 180)
            if not name:
                raise ValueError('A display name is required')
            db.execute('UPDATE subjects SET name=?,notes=?,updated_at=? WHERE id=?',
                       (name, text(payload.get('notes', ''), 12000), time.time(), case_id))
        elif action_name == 'photo':
            photo = text(payload.get('photo', ''), 55000)
            if photo:
                prefix = 'data:image/jpeg;base64,'
                if not photo.startswith(prefix):
                    raise ValueError('Only a locally prepared JPEG thumbnail is supported')
                try:
                    raw = base64.b64decode(photo[len(prefix):], validate=True)
                except ValueError:
                    raise ValueError('Invalid photo encoding')
                if len(raw) > 40000 or not raw.startswith(b'\xff\xd8\xff'):
                    raise ValueError('The photo must be a JPEG thumbnail below 40 KB')
            db.execute('UPDATE subjects SET photo=?,photo_source=?,updated_at=? WHERE id=?',
                       (photo, url(payload.get('source', '')), time.time(), case_id))
        elif action_name == 'observation':
            output = text(payload.get('output', ''), 30000)
            if not output:
                raise ValueError('Enter an observation or paste a tool result')
            add_observation(db, case_id, payload.get('tool', 'Manual import'), output, payload.get('source', ''))
        else:
            raise ValueError('Unknown casebook action')
    return dict(success=True, case_id=case_id)


def import_tiktok(value):
    """Import only public oEmbed metadata. No cookies, hidden identifiers or email inference."""
    parsed = urllib.parse.urlsplit(url(value))
    match = re.fullmatch(r'/@([A-Za-z0-9_.]{1,24})(?:/video/([0-9]{8,25}))?/?', parsed.path)
    if parsed.scheme != 'https' or parsed.hostname not in {'tiktok.com', 'www.tiktok.com'} or parsed.port not in {None, 443} or not match:
        raise ValueError('Enter a full HTTPS TikTok profile or video URL, not a shortened link')
    handle, video = match.groups()
    profile = 'https://www.tiktok.com/@' + handle
    source = profile + ('/video/' + video if video else '')
    metadata = None
    if video:
        endpoint = 'https://www.tiktok.com/oembed?' + urllib.parse.urlencode({'url': source})
        request = urllib.request.Request(endpoint, headers={'User-Agent': 'U1OS/2.0 personal-research', 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=9) as response:
                body = response.read(1_000_001)
            if len(body) > 1_000_000:
                raise ValueError('Response too large')
            metadata = json.loads(body)
            if not isinstance(metadata, dict) or metadata.get('type') != 'video' or not metadata.get('author_url'):
                raise ValueError('Public video metadata unavailable')
        except Exception:
            raise ValueError('TikTok did not return public video metadata. The video may be private, removed, restricted or temporarily unavailable. No hidden account data was accessed.')
    lines = ['TikTok public source: ' + source, 'Handle from supplied URL: @' + handle,
             'Profile reference: ' + profile, 'Identity and links to other accounts: unverified.',
             'Private linked email addresses: unavailable. No private account information was requested.']
    if metadata:
        lines.extend(['Public creator display name: ' + str(metadata.get('author_name', ''))[:200],
                      'Video title/caption: ' + str(metadata.get('title', ''))[:5000],
                      'Creator URL reported by TikTok: ' + str(metadata.get('author_url', ''))[:2000]])
        try:
            thumbnail = url(str(metadata.get('thumbnail_url', '')))
            if thumbnail:
                lines.append('Video thumbnail reference (not a verified profile photo): ' + thumbnail)
        except ValueError:
            pass
        lines.append('Public metadata from TikTok oEmbed. Embed scripts are not stored or executed.')
    else:
        lines.append('Profile URL saved as a research reference only. Add a public video URL to import supported oEmbed metadata.')
    with LOCK, connect() as db:
        case_id = upsert(db, 'tiktok:@' + handle, 'research')
        add_observation(db, case_id, 'TikTok public oEmbed' if metadata else 'TikTok profile reference', '\n'.join(lines), source)
    return dict(success=True, case_id=case_id, mode='public_video_metadata' if metadata else 'profile_reference',
                notice='Saved public reference information only. No private linked emails or hidden accounts are available through this importer.')
