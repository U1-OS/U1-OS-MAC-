"""Rights-confirmed source intake and official-export handoff, never a downloader.

No network client, cookie reader, subprocess launcher or arbitrary-file path is
used. Installing yt-dlp later does not silently enable network execution.
"""
import base64
import hmac
import importlib.util
import json
import re
import shutil
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from utils import integrations_hub

ENDPOINT = '/api/workspace/media-download'
MAX_BODY = 8192
MAX_URL = 2000
PROVIDERS = {
    'youtube': dict(name='YouTube', help_url='https://support.google.com/youtube/answer/56100?hl=en',
        guidance='For your own uploads, use YouTube Studio or Google Takeout. Official exports determine the available quality; Premium offline viewing is not a reusable original-file export.',
        guidance_status='official_guidance_reviewed'),
    'instagram': dict(name='Instagram', help_url='https://help.instagram.com/',
        guidance='Use your original file or consult the official Instagram Help Center for your account export options. Current export instructions could not be retrieved during this review.',
        guidance_status='help_center_handoff_only'),
    'tiktok': dict(name='TikTok', help_url='https://support.tiktok.com/en/using-tiktok/exploring-videos/video-downloads',
        guidance='Use Save video in TikTok when the creator allows downloading. If that option is absent, use your own original file or obtain an authorised copy from its creator.',
        guidance_status='official_guidance_reviewed'),
}


class IntakeError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def capabilities():
    try:
        installed = importlib.util.find_spec('yt_dlp') is not None or bool(shutil.which('yt-dlp'))
    except (ImportError, ValueError, OSError):
        installed = False
    return dict(success=True, mode='official_export_handoff', direct_download_available=False,
                yt_dlp_detected=installed, downloader_state='installed_not_enabled' if installed else 'not_installed',
                reason='Direct downloading is not enabled: redirect, DNS and media-CDN egress controls have not been implemented and verified.',
                providers=PROVIDERS, local_import_limit_bytes=25 * 1024 * 1024,
                quality_policy='Highest available within confirmed file/time budgets, if a future downloader is enabled. No resolution is promised or verified here.',
                network_requests=False, cookies=False, private_profiles=False, drm_bypass=False,
                watermark_removal=False, jobs=False)


def canonical_source(value):
    if (not isinstance(value, str) or not 0 < len(value) <= MAX_URL
            or not value.isascii() or any(c.isspace() or ord(c) < 32 for c in value)
            or '\\' in value or '%' in value):
        raise IntakeError('Use a direct HTTPS post URL without spaces or encoded paths.')
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or url.username is not None or url.password is not None
                or url.port not in {None, 443} or url.fragment):
            raise ValueError()
        query = parse_qs(url.query, keep_blank_values=True, max_num_fields=12)
    except ValueError:
        raise IntakeError('Use HTTPS on the standard port, without credentials or fragments.') from None
    if any(len(items) != 1 or len(items[0]) > 512 for items in query.values()):
        raise IntakeError('Duplicate or oversized URL parameters are not supported.')
    host, path = url.hostname, url.path
    if host in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'}:
        if set(query) - {'v', 'si', 't', 'feature'}:
            raise IntakeError('Use one direct YouTube video link without playlist or redirect parameters.')
        if host == 'youtu.be':
            identifier = path.strip('/') if path.count('/') <= 2 else ''
        elif path == '/watch':
            identifier = query.get('v', [''])[0]
        else:
            match = re.fullmatch(r'/shorts/([A-Za-z0-9_-]{11})/?', path)
            identifier = match[1] if match else ''
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', identifier):
            raise IntakeError('Use a single YouTube watch, Shorts or youtu.be video URL.')
        return 'youtube', 'https://www.youtube.com/watch?v=' + identifier
    if host in {'instagram.com', 'www.instagram.com'}:
        if set(query) - {'igsh', 'igshid', 'utm_source', 'utm_medium'}:
            raise IntakeError('Use a direct Instagram post or reel URL without redirect parameters.')
        match = re.fullmatch(r'/(p|reel)/([A-Za-z0-9_-]{5,64})/?', path)
        if not match:
            raise IntakeError('Use a single Instagram post or reel, not a profile or private-account link.')
        return 'instagram', 'https://www.instagram.com/' + match[1] + '/' + match[2] + '/'
    if host in {'tiktok.com', 'www.tiktok.com'}:
        if set(query) - {'_r', '_t', 'is_from_webapp', 'sender_device', 'web_id', 'lang'}:
            raise IntakeError('Use a direct TikTok video URL without redirect parameters.')
        match = re.fullmatch(r'/@([A-Za-z0-9_.]{1,24})/video/([0-9]{10,25})/?', path)
        if not match or match[1] in {'.', '..'}:
            raise IntakeError('Use a full TikTok video link. Profile and shortened redirect links are unsupported.')
        return 'tiktok', 'https://www.tiktok.com/@' + match[1] + '/video/' + match[2]
    raise IntakeError('Only direct YouTube, Instagram and TikTok post URLs are supported. No address is fetched.')


def action(body):
    if not isinstance(body, dict):
        raise IntakeError('Expected a JSON object.')
    if set(body) - {'action', 'url', 'rights_confirmed', 'public_unprotected_confirmed'}:
        raise IntakeError('Unsupported option. Cookies, headers, proxies, paths and watermark removal are not accepted.')
    if body.get('action') not in {'review_source', 'export_manifest'}:
        raise IntakeError('Direct downloads are unavailable. Use source review, official export or your local original.', 501)
    if body.get('rights_confirmed') is not True or body.get('public_unprotected_confirmed') is not True:
        raise IntakeError('Confirm your rights and that this is a public, unprotected post before reviewing it.')
    provider, canonical = canonical_source(body.get('url'))
    result = dict(success=True, provider=provider, provider_name=PROVIDERS[provider]['name'],
                  canonical_url=canonical, reviewed_at=datetime.now(timezone.utc).isoformat(),
                  rights_status='user_confirmed_not_independently_verified',
                  access_status='user_confirmed_public_unprotected_not_fetched',
                  media_downloaded=False, direct_download_available=False,
                  help_url=PROVIDERS[provider]['help_url'], guidance=PROVIDERS[provider]['guidance'],
                  watermark_policy='Preserve existing creator and platform marks. Use your own original file for an unwatermarked source.',
                  quality_checked=False, resolution=None, local_import_limit_bytes=25 * 1024 * 1024,
                  next_step='Use the official export option or obtain an authorised original, then open the local file in Media Studio.')
    if body['action'] == 'export_manifest':
        raw = json.dumps(dict(format='u1-media-intake-review', version=1, review=result), ensure_ascii=True, indent=2).encode()
        return dict(success=True, filename='media-source-review.json', mime='application/json', size=len(raw),
                    content=base64.b64encode(raw).decode(), media_downloaded=False)
    return result


def handle_request(handler):
    path = urlsplit(handler.path)
    if path.path != ENDPOINT:
        return False
    try:
        if not handler.integration_request_allowed():
            raise IntakeError('Local same-origin request required.', 403)
        if path.query:
            raise IntakeError('Query parameters are not supported. Source review uses a confirmed JSON request.')
        if handler.command == 'GET':
            handler.send_json(capabilities())
            return True
        if handler.command != 'POST':
            raise IntakeError('Use GET or POST.', 405)
        token = handler.headers.get('X-U1-CSRF', '')
        if not token or len(token) > 512 or not hmac.compare_digest(token.encode(), integrations_hub.CSRF_TOKEN.encode()):
            raise IntakeError('Reload the workspace before reviewing a source.', 403)
        if handler.headers.get('Transfer-Encoding'):
            raise IntakeError('Chunked requests are not supported.')
        if handler.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            raise IntakeError('Expected application/json.', 415)
        try:
            length = int(handler.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                raise ValueError()
            raw = handler.rfile.read(length)
            if len(raw) != length:
                raise ValueError()
            body = json.loads(raw)
        except (ValueError, TypeError, UnicodeError):
            raise IntakeError('Invalid or incomplete JSON request; maximum size is 8192 bytes.') from None
        handler.send_json(action(body))
    except IntakeError as error:
        handler.send_json(dict(success=False, error=str(error)), error.status)
    except Exception:
        handler.send_json(dict(success=False, error='Source review is unavailable. No media was downloaded.'), 503)
    return True
