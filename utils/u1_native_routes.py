"""One shell entry point and explicit native feature routing."""
import importlib
import json

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
    try:
        return importlib.import_module(module).handle_request(handler)
    except Exception:
        from utils.u1_safety import _reply
        _reply(handler, {'success': False, 'error': 'This native workspace could not complete the request. Its data has not been cleared.'}, 503)
        return True
