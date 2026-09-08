"""Read-only, fixed-path Desktop tool inventory. Never imports or launches tools."""
import json
import os
from pathlib import Path
import plistlib
import stat
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

ENDPOINT = '/api/workspace/osint-tools'
REPOSITORIES = Path("/Users/u1/Documents/ChatGPT/Repo's")
DESKTOP = Path('/Users/u1/Desktop')
MAX_METADATA = 16384
# IDs, names, bundle names, executables, evidence markers and links are application
# constants. Request input can select one ID, never supply a path or command.
TOOLS = (
    dict(id='dfw1n-osint', name='DFW1N OSINT', kind='Australian research resource guide',
         app='DFW1N OSINT.app', executable='DFW1NOSINT', bundle_id='local.dfw1nosint.guide',
         marker='README.md', local_url=None, config=False,
         docs='https://github.com/DFW1N/DFW1N-OSINT',
         note='Desktop launcher opens the local .local-guide.html resource guide.'),
    dict(id='gods-eye-view', name="God's Eye View", kind='Geospatial intelligence dashboard',
         app='Gods Eye View.app', executable=None, bundle_id=None, marker='package.json',
         local_url=None, config=False, docs='https://github.com/bilawalsidhu/gods-eye-view',
         note='Repository identified from package metadata. Its former Desktop bundle is currently absent; no live service is inferred.'),
    dict(id='holehe', name='Holehe', kind='Email account enumeration tool',
         app='Holehe.app', executable=None, bundle_id=None, marker='README.md',
         local_url=None, config=False, docs='https://github.com/megadose/holehe',
         note='Repository is inventoried only. Account enumeration is not connected, and the former Desktop bundle is absent.'),
    dict(id='maigret', name='Maigret', kind='Username research tool',
         app='Maigret.app', executable='Launcher', bundle_id='local.maigret.launcher', marker='pyproject.toml',
         local_url='http://127.0.0.1:4176/', config=True, docs='https://github.com/soxoj/maigret',
         note='Desktop configuration points to its own web wrapper. Automated person or username searches are not connected.'),
    dict(id='osiris', name='Osiris AI', kind='Local Next.js application',
         app='Osiris AI.app', executable='OsirisAI', bundle_id='local.osirisai.launcher', marker='package.json',
         local_url='http://localhost:4175/', config=True, docs=None,
         note='Desktop configuration points to the local standalone server. Provider credentials, billing and live feeds have not been checked.'),
    dict(id='ponytail', name='Ponytail', kind='Developer plugin, not an OSINT application',
         app=None, executable=None, bundle_id=None, marker='package.json', local_url=None, config=False,
         docs='https://github.com/DietrichGebert/ponytail',
         note='The eighth repository is a developer plugin. No corresponding Desktop OSINT launcher was discovered; plugin activation is not checked.'),
    dict(id='sherlock', name='Sherlock', kind='Username research tool',
         app='Sherlock.app', executable='Sherlock', bundle_id='local.sherlock.launcher', marker='pyproject.toml',
         local_url=None, config=False, docs='https://github.com/sherlock-project/sherlock',
         note='Desktop launcher opens a Terminal wrapper tied to this repository. No search or terminal is launched from U1.'),
    dict(id='spiderfoot', name='SpiderFoot', kind='OSINT automation framework',
         app='SpiderFoot.app', executable='Launcher', bundle_id='local.spiderfoot.launcher', marker='README.md',
         local_url='http://127.0.0.1:5001/', config=True, docs='https://github.com/smicallef/spiderfoot',
         note='Desktop configuration points to a loopback web server. Scan modules, accounts and external requests are not connected.'),
)


def path_state(path, directory=False):
    """Bounded lstat of a fixed path and its ancestors; never follows symlinks."""
    path = Path(path)
    try:
        for ancestor in reversed(path.parents):
            info = ancestor.lstat()
            if not stat.S_ISDIR(info.st_mode):
                return 'unsafe'
        info = path.lstat()
        correct = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if not correct or info.st_uid != os.getuid() or info.st_mode & 0o022:
            return 'unsafe'
        if not directory and info.st_nlink != 1:
            return 'unsafe'
        return 'present'
    except FileNotFoundError:
        return 'missing'
    except OSError:
        return 'unavailable'


def read_metadata(path):
    if path_state(path) != 'present':
        raise ValueError('Metadata is unavailable or needs review.')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_size > MAX_METADATA
                or info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_mode & 0o022):
            raise ValueError('Metadata is unavailable or exceeds the limit.')
        raw = stream.read(MAX_METADATA + 1)
    if len(raw) > MAX_METADATA:
        raise ValueError('Metadata exceeds the limit.')
    return raw


def tool_status(tool):
    repository = REPOSITORIES / tool['id']
    repo_state = path_state(repository, directory=True)
    marker_state = path_state(repository / tool['marker']) if repo_state == 'present' else repo_state
    app = DESKTOP / tool['app'] if tool['app'] else None
    launcher_state = path_state(app, directory=True) if app else 'not_applicable'
    mapping = 'repository_metadata_only'
    if launcher_state == 'present':
        if not tool['executable']:
            launcher_state = 'review_required'
        else:
            try:
                info = plistlib.loads(read_metadata(app / 'Contents' / 'Info.plist'))
                if (info.get('CFBundleIdentifier') != tool['bundle_id']
                        or info.get('CFBundleExecutable') != tool['executable']):
                    raise ValueError('Launcher identity changed.')
                executable = app / 'Contents' / 'MacOS' / tool['executable']
                if path_state(executable) != 'present':
                    raise ValueError('Launcher executable unavailable.')
                mapping = 'reviewed_launcher_mapping'
                if tool['config']:
                    config = json.loads(read_metadata(app / 'Contents' / 'Resources' / 'launcher.json'))
                    if not isinstance(config, dict) or config.get('repo') != str(repository) or config.get('url') != tool['local_url']:
                        raise ValueError('Launcher mapping changed.')
                    mapping = 'matching_launcher_configuration'
            except (OSError, ValueError, TypeError, AttributeError, plistlib.InvalidFileException):
                launcher_state, mapping = 'review_required', 'not_confirmed'
    if repo_state != 'present' or marker_state != 'present':
        state = 'setup_needed' if 'missing' in {repo_state, marker_state} else 'review_required'
    elif not app:
        state = 'plugin_only'
    elif launcher_state == 'present':
        state = 'desktop_only'
    elif launcher_state == 'missing':
        state = 'setup_needed'
    else:
        state = 'review_required'
    return dict(id=tool['id'], name=tool['name'], kind=tool['kind'], state=state,
                repository=dict(path=str(repository), state=repo_state, marker=tool['marker'], marker_state=marker_state),
                launcher=dict(path=str(app) if app else None, state=launcher_state, mapping=mapping),
                configured_local_url=tool['local_url'] if mapping == 'matching_launcher_configuration' else None,
                documentation_url=tool['docs'], note=tool['note'],
                runtime_status='not_checked', launch_available=False, query_available=False,
                limitation='Inventory only. Desktop processes, dependencies, accounts and network readiness are not tested.')


def snapshot(identifier=None):
    selected = TOOLS
    if identifier is not None:
        selected = tuple(tool for tool in TOOLS if tool['id'] == identifier)
        if not selected:
            raise ValueError('Unknown allowlisted tool ID.')
    items = [tool_status(tool) for tool in selected]
    return dict(success=True, checked_at=datetime.now(timezone.utc).isoformat(), tools=items,
                inventory_size=len(TOOLS), capabilities=dict(read_only=True, launch=False, query=False,
                    network_probe=False, external_documentation_links=True),
                notice='Eight repository candidates, not eight confirmed Desktop OSINT apps. Presence does not establish runtime readiness.')


def handle_request(handler):
    path = urlsplit(handler.path)
    if path.path != ENDPOINT:
        return False
    if not handler.integration_request_allowed():
        handler.send_json(dict(success=False, error='Local same-origin request required.'), 403)
        return True
    if handler.command != 'GET':
        handler.send_json(dict(success=False, error='This inventory is read-only. Launch and query actions are unavailable.'), 405)
        return True
    try:
        query = parse_qs(path.query, keep_blank_values=True)
        if set(query) - {'id'} or ('id' in query and len(query['id']) != 1):
            raise ValueError('Only one allowlisted tool ID is supported; paths, URLs and commands are not accepted.')
        handler.send_json(snapshot(query['id'][0] if 'id' in query else None))
    except ValueError as error:
        handler.send_json(dict(success=False, error=str(error)), 400)
    except Exception:
        handler.send_json(dict(success=False, error='Local tool metadata is unavailable.'), 503)
    return True
