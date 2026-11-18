"""Public /downloads page: official RustDesk installers preconfigured for this server.

Installers live in settings.DOWNLOADS_DIR (mounted read-only from the NAS):
    windows.exe        official rustdesk-<ver>-x86_64.exe
    mac-arm64.dmg      official rustdesk-<ver>-aarch64.dmg
    mac-x86_64.dmg     official rustdesk-<ver>-x86_64.dmg
    version.txt        the release version, e.g. 1.4.4

Windows is preconfigured by the download's file name: the RustDesk client reads
"rustdesk-licensed-<config code>.exe" at install time (src/custom_server.rs).
macOS installers can't carry settings, so the page shows the config code to
paste into Settings > Network.
"""
import base64
import binascii
import json
import os
import re

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import render

FILES = {
    'windows': ('windows.exe', 'application/vnd.microsoft.portable-executable'),
    'mac-arm64': ('mac-arm64.dmg', 'application/x-apple-diskimage'),
    'mac-x86_64': ('mac-x86_64.dmg', 'application/x-apple-diskimage'),
}


def _b64decode_any(s):
    s = s + '=' * (-len(s) % 4)
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            return decoder(s)
        except (binascii.Error, ValueError):
            continue
    raise ValueError('not base64')


def parse_config(code):
    """Decode a RustDesk config code (reversed base64 JSON) into a dict, or None."""
    if not code:
        return None
    try:
        data = json.loads(_b64decode_any(code.strip()[::-1]))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or not data.get('host'):
        return None
    return {k: str(data.get(k, '') or '') for k in ('host', 'relay', 'api', 'key')}


def filename_code(config):
    """Config code in the form the client parses from a file name:
    URL-safe base64 without padding (no '/', '+' or '='), reversed."""
    raw = json.dumps(config, separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')[::-1]


def _version():
    try:
        with open(os.path.join(settings.DOWNLOADS_DIR, 'version.txt')) as f:
            v = f.read().strip()
        return v if re.fullmatch(r'[0-9A-Za-z.\-]{1,20}', v) else ''
    except OSError:
        return ''


def _available():
    return {k for k, (name, _) in FILES.items()
            if os.path.isfile(os.path.join(settings.DOWNLOADS_DIR, name))}


def downloads(request):
    config = parse_config(settings.RUSTDESK_CONFIG)
    if not config:
        raise Http404()
    return render(request, 'downloads.html', {
        'config_code': settings.RUSTDESK_CONFIG,
        'host': config['host'],
        'version': _version(),
        'available': _available(),
    })


def download_file(request, platform):
    config = parse_config(settings.RUSTDESK_CONFIG)
    if not config or platform not in FILES:
        raise Http404()
    name, content_type = FILES[platform]
    path = os.path.join(settings.DOWNLOADS_DIR, name)
    if not os.path.isfile(path):
        raise Http404()
    version = _version()
    if platform == 'windows':
        filename = 'rustdesk-licensed-%s.exe' % filename_code(config)
    else:
        arch = 'aarch64' if platform == 'mac-arm64' else 'x86_64'
        filename = 'rustdesk-%s-%s.dmg' % (version or 'latest', arch)
    return FileResponse(open(path, 'rb'), as_attachment=True,
                        filename=filename, content_type=content_type)
