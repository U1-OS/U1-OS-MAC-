"""Explicitly billed OpenAI Images API adapter, scheduled by u1_assistant."""
import base64
import binascii
import hmac
import json
import os
from pathlib import Path
import re
import ssl
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit
import zlib

# The isolated Python worker imports only fixed local application modules.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import u1_assistant as assistant
from utils import u1_credentials as credentials

URL = 'https://api.openai.com/v1/images/generations'
MODEL = 'gpt-image-1.5'
MAX_PNG = 8 * 1024 * 1024
MAX_RESPONSE = 12 * 1024 * 1024
MAX_IMAGES = 20
_config_lock = threading.RLock()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _config(manager):
    try:
        data = json.loads(assistant._private_read(manager.root / 'image-provider.json', 4096))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}


def retained_artifact(job):
    """The same successful, retained job authorizes listing, reading and pinning.

    Never infer authorization from a PNG's presence or a caller-supplied path.
    MAX_IMAGES eviction and cancellation clear availability, releasing the pin.
    """
    artifact = job.get('artifact')
    return (job.get('kind') == 'image' and job.get('status') == 'succeeded'
            and isinstance(artifact, dict) and artifact.get('available') is True)


def snapshot(manager=None):
    service = manager or assistant.manager()
    config = _config(service)
    state = service.snapshot()
    configured = config.get('configured') is True
    helper = credentials.ready(service.root)
    jobs = [j for j in state['jobs'] if j.get('kind') == 'image']
    last_success = next((j for j in jobs if j['status'] == 'succeeded' and j.get('finished_at', 0) >= config.get('updated_at', 0)), None)
    return dict(success=True, adapter_installed=True, configured=configured,
                keychain_helper_ready=helper, ready_to_request=configured and helper,
                authorised=True if configured and last_success else None,
                state='configured_unverified' if configured and helper and not last_success else 'authorised' if configured and helper else 'setup_needed',
                model=MODEL, size='1024x1024', quality='low', output_format='png',
                billing='Separate OpenAI API billing. ChatGPT/Codex subscription allowance does not cover this API request. Exact price is not calculated here.',
                jobs=jobs, paused=state['paused'], storage_fault=state['storage_fault'],
                images=[dict(job_id=j['id'], title=j['title'], created_at=j['finished_at'], **j['artifact'])
                        for j in jobs if retained_artifact(j)])


def configure(body, manager=None):
    service = manager or assistant.manager()
    if body.get('confirmed') is not True:
        raise assistant.AssistantError('Confirm storage of this separate Images API credential.')
    with _config_lock:
        with service.condition:
            if any(j.get('kind') == 'image' and j['status'] in assistant.ACTIVE for j in service.jobs):
                raise assistant.AssistantError('Cancel or finish image jobs before changing the API credential.', 409)
        if body.get('action') == 'disconnect':
            if credentials.ready(service.root):
                credentials.operation(credentials.helper_path(service.root), 'delete')
            elif _config(service).get('configured'):
                raise assistant.AssistantError('Keychain helper unavailable; credential deletion was not confirmed.', 503)
            configured = False
        else:
            key = body.get('api_key')
            if not isinstance(key, str) or len(key) > 4096 or not re.fullmatch(r'sk-[A-Za-z0-9_-]{16,}', key):
                raise assistant.AssistantError('Enter a valid OpenAI API key.')
            helper = credentials.ensure_helper(service.root)
            if service.safety_check():
                raise assistant.AssistantError('Safety blocked credential setup before the Keychain write.', 423)
            credentials.operation(helper, 'set', dict(api_key=key))
            configured = True
        assistant._atomic_write(service.root / 'image-provider.json',
                                assistant._encoded(dict(configured=configured, updated_at=time.time())))
    return snapshot(service)


def submit(body, manager=None):
    service = manager or assistant.manager()
    if body.get('confirmed_api_billing') is not True:
        raise assistant.AssistantError('Review this image prompt and explicitly confirm separate OpenAI API billing.')
    if set(body) - {'action', 'request_id', 'prompt', 'confirmed_api_billing'}:
        raise assistant.AssistantError('Unsupported image option. This action creates one low-quality 1024x1024 PNG.')
    with _config_lock:
        if not _config(service).get('configured') or not credentials.ready(service.root):
            raise assistant.AssistantError('Images API setup is needed. Save a separate API key to Keychain first.', 409)
        return service.submit(dict(confirmed=True, request_id=body.get('request_id'),
                                   role='Design', prompt=body.get('prompt'), context=[]), kind='image')


def worker_command(root, output):
    return [sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--worker',
            str(credentials.helper_path(root)), str(output)]


def validate_png(content):
    """Validate actual PNG structure, CRCs and bounded decoded scanlines, not a suffix."""
    if not 45 <= len(content) <= MAX_PNG or not content.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('The provider did not return a supported PNG.')
    offset, width, height, channels = 8, 0, 0, 0
    image_data = bytearray()
    seen_header = seen_end = False
    while offset + 12 <= len(content):
        length = struct.unpack('>I', content[offset:offset + 4])[0]
        kind = content[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(content) or length > MAX_PNG:
            raise ValueError('Invalid PNG chunk size.')
        chunk = content[offset + 8:offset + 8 + length]
        checksum = struct.unpack('>I', content[offset + 8 + length:end])[0]
        if zlib.crc32(kind + chunk) & 0xffffffff != checksum:
            raise ValueError('Invalid PNG checksum.')
        if not seen_header and kind != b'IHDR':
            raise ValueError('PNG header missing.')
        if kind == b'IHDR':
            if seen_header or length != 13:
                raise ValueError('Invalid PNG header.')
            width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', chunk)
            channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color, 0)
            if (width, height) != (1024, 1024) or depth != 8 or not channels or compression or filtering or interlace:
                raise ValueError('Unsupported PNG dimensions or encoding.')
            seen_header = True
        elif kind == b'IDAT':
            image_data.extend(chunk)
        elif kind == b'IEND':
            if length or end != len(content):
                raise ValueError('Invalid PNG end marker.')
            seen_end = True
            break
        elif kind == b'acTL' or not kind[:1].islower() and kind != b'PLTE':
            raise ValueError('Unsupported PNG chunk.')
        offset = end
    if not seen_header or not seen_end or not image_data:
        raise ValueError('Incomplete PNG.')
    expected = (width * channels + 1) * height
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(bytes(image_data), expected + 1)
    if len(decoded) != expected or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
        raise ValueError('Invalid or excessive PNG pixel data.')
    stride = width * channels + 1
    if any(decoded[row * stride] > 4 for row in range(height)):
        raise ValueError('Invalid PNG scanline filter.')
    return dict(width=width, height=height, bytes=len(content), mime='image/png')


def request_image(payload, key):
    if not isinstance(key, str) or not re.fullmatch(r'sk-[A-Za-z0-9_-]{16,}', key) or len(key) > 4096:
        raise ValueError('Image credential unavailable.')
    request = urllib.request.Request(URL, data=assistant._encoded(payload), method='POST',
                                     headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                                              'Accept': 'application/json', 'User-Agent': 'U1OS/Images'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(request, timeout=150) as response:
        if response.geturl() != URL or response.status != 200:
            raise ValueError('Image provider request declined.')
        if response.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise ValueError('Unexpected image provider response.')
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError('Image provider response exceeded the size limit.')
    data = json.loads(raw)
    entries = data.get('data') if isinstance(data, dict) else None
    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
        raise ValueError('Image provider returned no usable image.')
    encoded = entries[0].get('b64_json')
    if not isinstance(encoded, str) or len(encoded) > (MAX_PNG * 4 // 3 + 8):
        raise ValueError('Image provider response exceeded the size limit.')
    content = base64.b64decode(encoded, validate=True)
    validate_png(content)
    return content


def store_result(service, job, content):
    info = validate_png(content)
    directory = service.root / 'images'
    assistant._private_dir(directory)
    with service.condition:
        if service.cancel_requested.is_set():
            raise ValueError('Image request cancelled.')
        assistant._atomic_write(directory / (job['id'] + '.png'), content)
        job['artifact'] = dict(info, available=True,
                               url='/api/workspace/image-provider?image_id=' + job['id'])
        # Only generated names in the owned directory are eligible for retention.
        files = [p for p in directory.glob('*.png') if re.fullmatch(r'[0-9a-f]{32}\.png', p.name)]
        for old in sorted(files, key=lambda p: p.lstat().st_mtime, reverse=True)[MAX_IMAGES:]:
            old.unlink()
            for previous in service.jobs:
                if previous['id'] == old.stem and previous.get('artifact'):
                    previous['artifact']['available'] = False


def discard_result(service, job):
    (service.root / 'images' / (assistant._id(job['id']) + '.png')).unlink(missing_ok=True)
    job['artifact']['available'] = False


def _image_reply(handler, service, identifier):
    identifier = assistant._id(identifier)
    with service.condition:
        found = next((j for j in service.jobs if j['id'] == identifier and retained_artifact(j)), None)
        if found is None:
            raise assistant.AssistantError('Image not found or no longer retained.', 404)
        content = assistant._private_read(service.root / 'images' / (identifier + '.png'), MAX_PNG)
    validate_png(content)
    handler.send_response(200)
    for name, value in [('Content-Type', 'image/png'), ('Content-Length', str(len(content))),
                        ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                        ('Content-Disposition', 'inline; filename="u1-image-' + identifier + '.png"'),
                        ('Content-Security-Policy', "default-src 'none'; sandbox"), ('Connection', 'close')]:
        handler.send_header(name, value)
    handler.end_headers()
    handler.close_connection = True
    handler.wfile.write(content)


def handle_request(handler):
    """True iff /api/workspace/image-provider was handled. Call after Safety gate."""
    path = urlsplit(handler.path)
    if path.path != '/api/workspace/image-provider':
        return False
    try:
        if not handler.integration_request_allowed():
            raise assistant.AssistantError('Local same-origin request required.', 403)
        if handler.command == 'GET':
            identifier = parse_qs(path.query).get('image_id', [None])[0]
            if identifier:
                _image_reply(handler, assistant.manager(), identifier)
            else:
                assistant._reply(handler, snapshot())
            return True
        if handler.command != 'POST':
            raise assistant.AssistantError('Method not allowed.', 405)
        from utils.integrations_hub import CSRF_TOKEN
        if not hmac.compare_digest(handler.headers.get('X-U1-CSRF', '').encode(), CSRF_TOKEN.encode()):
            raise assistant.AssistantError('Reload the workspace before running an action.', 403)
        if handler.headers.get('Transfer-Encoding'):
            raise assistant.AssistantError('Unsupported request encoding.')
        if handler.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            raise assistant.AssistantError('Expected application/json.', 415)
        try:
            length = int(handler.headers.get('Content-Length', '0'))
        except (ValueError, TypeError):
            raise assistant.AssistantError('Invalid request size.') from None
        if not 0 < length <= assistant.MAX_BODY:
            raise assistant.AssistantError('Invalid request size.', 413)
        raw = handler.rfile.read(length)
        if len(raw) != length:
            raise assistant.AssistantError('Incomplete request.')
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            raise assistant.AssistantError('Invalid JSON request.') from None
        if not isinstance(body, dict):
            raise assistant.AssistantError('Expected a JSON object.')
        if body.get('action') in {'configure', 'disconnect'}:
            result = configure(body)
            code = 200
        elif body.get('action') == 'generate':
            result = submit(body)
            code = 202
        else:
            raise assistant.AssistantError('Unknown image provider action.')
        assistant._reply(handler, result, code)
    except assistant.AssistantError as error:
        assistant._reply(handler, dict(success=False, error=str(error)), error.status)
    except Exception:
        assistant._reply(handler, dict(success=False, error='The image provider operation did not complete. Keychain or API details were not logged.'), 503)
    return True


def worker_main():
    """Invoked only as the manager's owned child. Never prints a key or API error."""
    try:
        if len(sys.argv) != 4 or sys.argv[1] != '--worker':
            return 1
        raw = sys.stdin.buffer.read(assistant.MAX_BODY + 1)
        if len(raw) > assistant.MAX_BODY:
            return 1
        data = json.loads(raw)
        # Rebuild the fixed request: no URL, model, quality, size or count override.
        prompt = assistant._text(data.get('prompt'), assistant.MAX_PROMPT, True)
        payload = dict(model=MODEL, prompt=prompt, n=1, size='1024x1024', quality='low', output_format='png')
        stored = credentials.operation(Path(sys.argv[2]), 'get')
        key = stored.get('api_key')
        content = request_image(payload, key)
        del key, stored
        output = Path(sys.argv[3])
        assistant._private_read(output, MAX_PNG)  # Existing owner-only regular file required.
        fd = os.open(output, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        return 0
    except Exception:
        return 1


if __name__ == '__main__':
    raise SystemExit(worker_main())
