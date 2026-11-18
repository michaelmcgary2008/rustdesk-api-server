"""Sign in with Google for the RustDesk client and the web UI.

Client protocol (rustdesk src/hbbs_http/account.rs, flutter user_model.dart):
  GET  /api/login-options             -> ["oidc/google"]
  POST /api/oidc/auth                 {op, id, uuid, deviceInfo} -> {code, url}
       The client opens `url` in the browser, then polls once a second (3 min):
  GET  /api/oidc/auth-query?code&id&uuid
       pending  -> {"error": "No authed oidc is found"}   (client keeps polling)
       done     -> {access_token, type: "access_token", user: {...}}
       failure  -> {"error": "<message>"}                 (client stops)
Google redirects the browser to /api/oidc/callback?code&state.
Web UI: /api/oidc/web-login starts the same flow and logs the browser in.
"""
import base64
import datetime
import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib import auth
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render

from api.models import GoogleIdentity, OidcSession, RustDeskToken, UserProfile

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_ISSUERS = ('https://accounts.google.com', 'accounts.google.com')
PENDING = 'No authed oidc is found'
SESSION_MINUTES = 10
logger = logging.getLogger(__name__)


def _google_error(http_error):
    """Google's error code only (never echoes request data or secrets)."""
    try:
        return str(json.loads(http_error.read().decode()).get('error', ''))[:60]
    except (ValueError, UnicodeDecodeError, OSError, AttributeError):
        return ''


def enabled():
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET
                and settings.GOOGLE_REDIRECT_URI and settings.GOOGLE_ALLOWED_DOMAINS)


def _now():
    return datetime.datetime.now()


def _cleanup():
    OidcSession.objects.filter(created__lt=_now() - datetime.timedelta(minutes=SESSION_MINUTES)).delete()


def _google_url(session):
    params = {
        'client_id': settings.GOOGLE_CLIENT_ID,
        'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': session.state,
        'prompt': 'select_account',
    }
    if len(settings.GOOGLE_ALLOWED_DOMAINS) == 1:
        params['hd'] = settings.GOOGLE_ALLOWED_DOMAINS[0]  # UI hint only; enforced below
    return GOOGLE_AUTH_URL + '?' + urllib.parse.urlencode(params)


def _new_session(op, rid='', uuid='', device_info=''):
    _cleanup()
    return OidcSession.objects.create(
        code=secrets.token_urlsafe(32), state=secrets.token_urlsafe(32), op=op[:20],
        rid=rid[:60], uuid=uuid[:100], device_info=device_info)


# ---------- RustDesk client endpoints ----------

def login_options(request):
    return JsonResponse(['oidc/google'] if enabled() else [], safe=False)


def oidc_auth(request):
    if request.method != 'POST' or not enabled():
        return JsonResponse({'error': 'Google sign-in is not available.'})
    try:
        data = json.loads(request.body.decode() or '{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid request.'}, status=400)
    if str(data.get('op', '')).lower() != 'google':
        return JsonResponse({'error': 'Unsupported sign-in provider.'})
    session = _new_session('google', str(data.get('id', '')), str(data.get('uuid', '')),
                           json.dumps(data.get('deviceInfo', '')))
    return JsonResponse({'code': session.code, 'url': _google_url(session)})


def oidc_auth_query(request):
    code = request.GET.get('code', '')
    session = OidcSession.objects.filter(code=code).first() if code else None
    if (not session or session.op == 'web'
            or session.created < _now() - datetime.timedelta(minutes=SESSION_MINUTES)):
        return JsonResponse({'error': 'Sign-in expired. Please try again.'})
    if session.rid != request.GET.get('id', '') or session.uuid != request.GET.get('uuid', ''):
        return JsonResponse({'error': 'Invalid request.'})
    if not session.user_id:
        if session.error:
            msg = session.error
            session.delete()
            return JsonResponse({'error': msg})
        return JsonResponse({'error': PENDING})
    user = session.user
    with transaction.atomic():
        deleted, _ = OidcSession.objects.filter(pk=session.pk).delete()
        if not deleted:  # another poll already consumed it
            return JsonResponse({'error': PENDING})
        token = _issue_token(user, session.rid, session.uuid, session.device_info)
    return JsonResponse({
        'access_token': token.access_token,
        'type': 'access_token',
        # Client's UserPayload (src/hbbs_http/account.rs) REQUIRES `name` and
        # `info`; without `info` the client can't parse the reply, keeps
        # polling, and then sees the already-consumed code as expired.
        'user': {
            'name': user.username,
            'display_name': user.username,
            'email': user.username if '@' in user.username else '',
            'note': '',
            'status': 1,
            'info': {},
            'is_admin': bool(user.is_admin),
        },
    })


def _issue_token(user, rid, uuid, device_info):
    """Same token semantics as the password login in views_api.login."""
    user.rid = rid
    user.uuid = uuid
    user.rtype = 'oidc'
    user.deviceInfo = device_info
    user.save()
    RustDeskToken.objects.filter(Q(uid=user.id) & Q(rid=rid)).delete()
    return RustDeskToken.objects.create(
        username=user.username[:20], uid=user.id, uuid=uuid[:60], rid=rid[:16],
        access_token=secrets.token_hex(24))


# ---------- Web UI ----------

WEB_STATE_KEY = 'oidc_web_state'


def web_login(request):
    if not enabled():
        return HttpResponseRedirect('/api/user_action?action=login')
    session = _new_session('web')
    # Bind the attempt to this browser: only the browser holding this Django
    # session may finish it, so a link-preview bot or anyone else who opens
    # the callback URL first can neither consume nor hijack the login.
    request.session[WEB_STATE_KEY] = session.state
    return HttpResponseRedirect(_google_url(session))


# ---------- Google redirect ----------

def _exchange(code):
    body = urllib.parse.urlencode({
        'code': code,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code',
    }).encode()
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=body,
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _id_token_claims(id_token):
    # The ID token comes straight from Google's token endpoint over TLS, so per
    # OpenID Connect Core 3.1.3.7 its signature need not be re-verified; the
    # claims below are still checked.
    payload = id_token.split('.')[1]
    payload += '=' * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def _check_claims(claims):
    """Return (email, sub) or raise ValueError with a user-facing message."""
    if claims.get('aud') != settings.GOOGLE_CLIENT_ID or claims.get('iss') not in GOOGLE_ISSUERS:
        raise ValueError('Google sign-in could not be verified.')
    if int(claims.get('exp', 0)) < int(datetime.datetime.now(datetime.timezone.utc).timestamp()):
        raise ValueError('Google sign-in expired. Please try again.')
    email = str(claims.get('email', '')).strip().lower()
    hd = str(claims.get('hd', '')).lower()
    domain = email.rsplit('@', 1)[-1] if '@' in email else ''
    allowed = settings.GOOGLE_ALLOWED_DOMAINS
    if not claims.get('email_verified') or not email or domain not in allowed or hd not in allowed:
        raise ValueError('Only Waters Church Google accounts can sign in (%s).' % ', '.join(allowed))
    sub = str(claims.get('sub', ''))
    if not sub:
        raise ValueError('Google sign-in could not be verified.')
    return email, sub


@transaction.atomic
def _user_for(email, sub):
    ident = (GoogleIdentity.objects.select_for_update().filter(sub=sub).first()
             or GoogleIdentity.objects.select_for_update().filter(email=email).first())
    if ident:
        if ident.sub and ident.sub != sub:
            raise ValueError('This email is linked to a different Google account.')
        ident.sub = sub
        ident.email = email
        ident.last_login = _now()
        ident.save()
        user = ident.user
    else:
        user = UserProfile.objects.filter(username__iexact=email).first()
        if not user:
            user = UserProfile(username=email[:50], is_admin=False, is_active=True)
            user.set_unusable_password()
            user.save()
        GoogleIdentity.objects.create(user=user, email=email, sub=sub, last_login=_now())
    if not user.is_active:
        raise ValueError('This account is disabled.')
    return user


PREVIEW_BOT_MARKERS = ('facebookexternalhit', 'facebot', 'twitterbot', 'slackbot', 'linkedinbot',
                       'discordbot', 'whatsapp', 'telegrambot', 'skypeuripreview', 'googlebot',
                       'bingbot', 'embedly', 'preview')


def _is_preview_bot(request):
    ua = request.META.get('HTTP_USER_AGENT', '').lower()
    return any(m in ua for m in PREVIEW_BOT_MARKERS)


def callback(request):
    if _is_preview_bot(request):
        # Link previews (Apple's identifies as facebookexternalhit/Twitterbot)
        # fetch this URL alongside the real browser; never let them spend
        # Google's single-use code.
        return _done(request, False, 'Open this link in a web browser to sign in.')
    state = request.GET.get('state', '')
    session = OidcSession.objects.filter(state=state).first() if state else None
    if not session or session.created < _now() - datetime.timedelta(minutes=SESSION_MINUTES):
        return _done(request, False, 'This sign-in link has expired. Start again from RustDesk.')
    if session.op == 'web' and request.session.get(WEB_STATE_KEY) != state:
        # Not the browser that started this web login: leave the attempt intact.
        return _done(request, False, 'Open this sign-in from the same browser you started it in.')
    if session.op != 'web' and (session.user_id or session.error):
        # Already finished (e.g. a link preview fetched this URL first; Google
        # codes are single-use). The RustDesk app gets the result either way.
        if session.user_id:
            return _done(request, True, 'Signed in. You can close this window and return to RustDesk.')
        return _done(request, False, session.error)
    try:
        if request.GET.get('error'):
            raise ValueError('Google sign-in was cancelled.')
        tokens = _exchange(request.GET.get('code', ''))
        email, sub = _check_claims(_id_token_claims(tokens.get('id_token', '')))
        user = _user_for(email, sub)
    except ValueError as e:
        msg = str(e)
    except urllib.error.HTTPError as e:
        logger.warning('Google token exchange failed: HTTP %s %s', e.code, _google_error(e))
        msg = 'Google rejected the sign-in. Please try again.'
    except (urllib.error.URLError, OSError) as e:
        logger.warning('Google token exchange failed: %s', e)
        msg = 'Could not reach Google. Please try again.'
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        logger.warning('Unexpected Google token response: %s', type(e).__name__)
        msg = 'Google sign-in could not be verified.'
    else:
        if session.op == 'web':
            session.delete()
            auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')  # rotates the session
            return HttpResponseRedirect('/api/work')
        OidcSession.objects.filter(pk=session.pk).update(user=user, error='')
        return _done(request, True, 'Signed in as %s. You can close this window and return to RustDesk.' % email)
    if session.op == 'web':
        session.delete()
        return _done(request, False, msg)
    # Two requests can race here (Google codes are single-use): never let a
    # failure overwrite a sign-in that already succeeded.
    OidcSession.objects.filter(pk=session.pk, user__isnull=True).update(error=msg[:200])
    if OidcSession.objects.filter(pk=session.pk, user__isnull=False).exists():
        return _done(request, True, 'Signed in. You can close this window and return to RustDesk.')
    return _done(request, False, msg)


def _done(request, ok, message):
    return render(request, 'oidc_done.html', {'ok': ok, 'message': message}, status=200 if ok else 400)
