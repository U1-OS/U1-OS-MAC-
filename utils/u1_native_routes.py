"""One shell entry point and explicit native feature routing."""
import importlib
import hmac
import json
from urllib.parse import parse_qs

# Exact operational routes only. The server calls Safety before this module;
# retain local-origin and CSRF checks before dispatching these new surfaces.
OPERATIONAL_HANDLERS = {
    '/api/workspace/activation': 'utils.u1_connection_preflight',
    '/api/workspace/spotify': 'utils.u1_spotify',
    '/api/workspace/osint-tools': 'utils.u1_osint_tools',
    '/api/workspace/media-download': 'utils.u1_media_download',
    '/api/workspace/discovery': 'utils.u1_discovery',
}

HANDLERS = {
    '/api/workspace/studio-pro': 'utils.u1_studio_pro',
    '/api/workspace/personal': 'utils.u1_personal_core',
    '/api/workspace/personal/export': 'utils.u1_personal_core',
    '/api/workspace/personal/snapshot': 'utils.u1_personal_core',
    '/api/workspace/assistant': 'utils.u1_assistant',
    '/api/workspace/jobs': 'utils.u1_assistant',
    '/api/workspace/image-provider': 'utils.u1_image_provider',
    '/api/workspace/private-backup': 'utils.u1_private_backup',
    '/api/workspace/media-research': 'utils.u1_media_research',
    **OPERATIONAL_HANDLERS,
}
OLD_ENTRIES = {'/classic': 'home', '/classic/': 'home', '/studio.html': 'studio',
               '/integrations.html': 'integrations', '/prism.html': 'home'}


def handle_request(handler):
    path = handler.path.split('?', 1)[0]
    if handler.command == 'GET' and path in OLD_ENTRIES:
        default = json.dumps(OLD_ENTRIES[path])
        content = ('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Opening U1 OS</title><style>body{background:#071422;color:#d7ecff;font:16px sans-serif;padding:8vw}a{color:#5cddff}</style><h1>Opening your U1 OS workspace</h1><p>The old shell has been replaced. Your underlying local records are preserved.</p><a href="/">Open U1 OS</a><script>
var destination=''' + default + ''';
try{var old=decodeURIComponent(location.hash.slice(1)).replace(/^(?:legacy:)+/,'');var map={home:'home',ai:'ai',ai_workbench:'ai',studio:'studio',media:'media',osint:'osint',crypto:'crypto',trading:'trading',finance:'income',business:'income',comms:'communications',communications:'communications',projects:'projects',tasks:'tasks',calendar:'calendar',files:'files',notes:'notes',automation:'automation',settings:'settings',system:'system',updater:'updater',integrations:'integrations'};if(map[old])destination=map[old];}catch(e){}
location.replace('/#'+encodeURIComponent(destination));
</script></html>''').encode('utf-8')
        handler.send_response(200)
        handler.send_header('Content-Type', 'text/html; charset=utf-8')
        handler.send_header('Content-Length', str(len(content)))
        handler.send_header('Cache-Control', 'no-store')
        handler.end_headers()
        handler.wfile.write(content)
        return True
    module = HANDLERS.get(path)
    if not module:
        return False
    if path in OPERATIONAL_HANDLERS:
        methods = {'GET'} if path in {'/api/workspace/activation', '/api/workspace/osint-tools', '/api/workspace/discovery'} else {'GET', 'POST'}
        if handler.command not in methods:
            handler.send_json({'success': False, 'error': 'Method not supported on this exact workspace endpoint.'}, 405)
            return True
        allowed = getattr(handler, 'integration_request_allowed', None)
        if not callable(allowed) or not allowed():
            handler.send_json({'success': False, 'error': 'Local same-origin request required.'}, 403)
            return True
        if handler.command == 'POST':
            from utils import integrations_hub
            token = handler.headers.get('X-U1-CSRF', '')
            if not isinstance(token, str) or len(token) > 512 or not hmac.compare_digest(token.encode('utf-8'), integrations_hub.CSRF_TOKEN.encode('utf-8')):
                handler.send_json({'success': False, 'error': 'Reload U1 OS for local authorisation before running this action.'}, 403)
                return True
    try:
        target = importlib.import_module(module)
        if path == '/api/workspace/discovery':
            try:
                raw_query = handler.path.partition('?')[2]
                if len(raw_query) > 2048:
                    raise ValueError('Discovery query is too long.')
                query = parse_qs(raw_query, keep_blank_values=True, max_num_fields=8)
                payload = target.handle_get(query)
            except ValueError as error:
                handler.send_json({'success': False, 'error': str(error)[:240]}, 400)
            else:
                handler.send_json(payload)
            return True
        return target.handle_request(handler)
    except Exception:
        from utils.u1_safety import _reply
        _reply(handler, {'success': False, 'error': 'This native workspace could not complete the request. Its data has not been cleared.'}, 503)
        return True
