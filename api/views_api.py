# cython:language_level=3
from django.http import JsonResponse
import json
import time
import datetime
# import hashlib
import math
from django.contrib import auth
# from django.forms.models import model_to_dict
from api.models import RustDeskToken, UserProfile, RustDeskTag, RustDeskPeer, RustDesDevice, ConnLog, FileLog
from django.db.models import Q
import copy
from .views_front import *
from django.utils.translation import gettext as _


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def parse_json_body(request):
    """Parse the request body as JSON.

    Returns (data, None) on success or (None, JsonResponse) on a malformed
    body, so client-facing endpoints return a clean 400 instead of a 500.
    """
    try:
        return json.loads(request.body.decode()), None
    except (ValueError, UnicodeDecodeError):
        return None, JsonResponse({'error': _('Invalid JSON body.')}, status=400)


def login(request):
    result = {}
    if request.method == 'GET':
        result['error'] = _('Wrong method. Use POST.')
        return JsonResponse(result)

    data, err = parse_json_body(request)
    if err:
        return err

    username = data.get('username', '')
    password = data.get('password', '')
    rid = data.get('id', '')
    uuid = data.get('uuid', '')
    autoLogin = data.get('autoLogin', True)
    rtype = data.get('type', '')
    deviceInfo = data.get('deviceInfo', '')
    user = auth.authenticate(username=username, password=password)
    if not user:
        result['error'] = _('Invalid username or password. Too many attempts may lock your IP.')
        return JsonResponse(result)
    user.rid = rid
    user.uuid = uuid
    user.autoLogin = autoLogin
    user.rtype = rtype
    user.deviceInfo = json.dumps(deviceInfo)
    user.save()
    # Bind device (20240819)
    peer = RustDeskPeer.objects.filter(Q(rid=rid)).first()
    if not peer:
        device = RustDesDevice.objects.filter(Q(uuid=uuid)).first()
        if device:
            peer = RustDeskPeer()
            peer.uid = user.id
            peer.rid = device.rid
            # peer.abid = ab.guid    # v2,  current version not used
            peer.hostname = device.hostname
            peer.username = device.username
            peer.save()

    token = RustDeskToken.objects.filter(Q(uid=user.id) & Q(username=user.username) & Q(rid=user.rid)).first()

    # Check token expiry (total_seconds, not .seconds — the latter drops whole days)
    if token:
        age = (datetime.datetime.now() - token.create_time).total_seconds()
        if age >= EFFECTIVE_SECONDS:
            token.delete()
            token = None

    if not token:
        # Create and store token
        token = RustDeskToken(
            username=user.username,
            uid=user.id,
            uuid=user.uuid,
            rid=user.rid,
            access_token=getStrMd5(str(time.time()) + salt)
        )
        token.save()

    result['access_token'] = token.access_token
    result['type'] = 'access_token'
    result['user'] = {'name': user.username}
    return JsonResponse(result)


def logout(request):
    if request.method == 'GET':
        result = {'error': _('Wrong method.')}
        return JsonResponse(result)

    data, err = parse_json_body(request)
    if err:
        return err
    rid = data.get('id', '')
    uuid = data.get('uuid', '')
    user = UserProfile.objects.filter(Q(rid=rid) & Q(uuid=uuid)).first()
    if not user:
        result = {'error': _('Invalid request.')}
        return JsonResponse(result)
    token = RustDeskToken.objects.filter(Q(uid=user.id) & Q(rid=user.rid)).first()
    if token:
        token.delete()

    result = {'code': 1}
    return JsonResponse(result)


def currentUser(request):
    result = {}
    if request.method == 'GET':
        result['error'] = _('Wrong submission method.')
        return JsonResponse(result)
    # postdata = json.loads(request.body)
    # rid = postdata.get('id', '')
    # uuid = postdata.get('uuid', '')

    access_token = request.META.get('HTTP_AUTHORIZATION', '')
    access_token = access_token.split('Bearer ')[-1]
    token = RustDeskToken.objects.filter(Q(access_token=access_token)).first()
    user = None
    if token:
        user = UserProfile.objects.filter(Q(id=token.uid)).first()

    if user:
        if token:
            result['access_token'] = token.access_token
        result['type'] = 'access_token'
        result['name'] = user.username
    return JsonResponse(result)


def ab(request):
    '''
    '''
    access_token = request.META.get('HTTP_AUTHORIZATION', '')
    access_token = access_token.split('Bearer ')[-1]
    token = RustDeskToken.objects.filter(Q(access_token=access_token)).first()
    if not token:
        result = {'error': _('Failed to load address book.')}
        return JsonResponse(result)

    if request.method == 'GET':
        result = {}
        uid = token.uid
        tags = RustDeskTag.objects.filter(Q(uid=uid))
        tag_names = []
        tag_colors = {}
        if tags:
            tag_names = [str(x.tag_name) for x in tags]
            tag_colors = {str(x.tag_name): int(x.tag_color) for x in tags if x.tag_color != ''}

        peers_result = []
        peers = RustDeskPeer.objects.filter(Q(uid=uid))
        if peers:
            for peer in peers:
                tmp = {
                    'id': peer.rid,
                    'username': peer.username,
                    'hostname': peer.hostname,
                    'alias': peer.alias,
                    'platform': peer.platform,
                    'tags': peer.tags.split(','),
                    'hash': peer.rhash,
                }
                peers_result.append(tmp)

        result['updated_at'] = datetime.datetime.now()
        result['data'] = {
            'tags': tag_names,
            'peers': peers_result,
            'tag_colors': json.dumps(tag_colors)
        }
        result['data'] = json.dumps(result['data'])
        return JsonResponse(result)
    else:
        postdata, err = parse_json_body(request)
        if err:
            return err
        data = postdata.get('data', '')
        try:
            data = {} if data == '' else json.loads(data)
        except (TypeError, ValueError):
            return JsonResponse({'error': _('Invalid JSON body.')}, status=400)
        tagnames = data.get('tags', [])
        tag_colors = data.get('tag_colors', '')
        tag_colors = {} if tag_colors == '' else json.loads(tag_colors)
        peers = data.get('peers', [])

        if tagnames:
            RustDeskTag.objects.filter(uid=token.uid).delete()
            newlist = []
            for name in tagnames:
                tag = RustDeskTag(
                    uid=token.uid,
                    tag_name=name,
                    tag_color=tag_colors.get(name, '')
                )
                newlist.append(tag)
            RustDeskTag.objects.bulk_create(newlist)
        if peers:
            RustDeskPeer.objects.filter(uid=token.uid).delete()
            newlist = []
            for one in peers:
                peer = RustDeskPeer(
                    uid=token.uid,
                    rid=one['id'],
                    username=one['username'],
                    hostname=one['hostname'],
                    alias=one['alias'],
                    platform=one['platform'],
                    tags=','.join(one['tags']),
                    rhash=one['hash'],


                )
                newlist.append(peer)
            RustDeskPeer.objects.bulk_create(newlist)

    result = {
        'code': 102,
        'data': _('Address book update error')
    }
    return JsonResponse(result)


def ab_get(request):
    # x86-sciter client uses POST /api/ab/get for address book
    request.method = 'GET'
    return ab(request)


def sysinfo(request):
    # Clients send device info after the service is registered
    result = {}
    if request.method == 'GET':
        result['error'] = _('Wrong submission method.')
        return JsonResponse(result)
    client_ip = get_client_ip(request)
    postdata, err = parse_json_body(request)
    if err:
        return err
    if 'id' not in postdata or 'uuid' not in postdata:
        return JsonResponse({'error': _('Invalid request.')}, status=400)
    device = RustDesDevice.objects.filter(Q(rid=postdata['id']) & Q(uuid=postdata['uuid'])).first()
    if not device:
        device = RustDesDevice(
            rid=postdata['id'],
            cpu=postdata['cpu'],
            hostname=postdata['hostname'],
            memory=postdata['memory'],
            os=postdata['os'],
            username=postdata.get('username', '-'),
            uuid=postdata['uuid'],
            version=postdata['version'],
            ip_address=client_ip
        )
        device.save()
    else:
        postdata2 = copy.copy(postdata)
        postdata2['rid'] = postdata2['id']
        postdata2.pop('id')
        RustDesDevice.objects.filter(Q(rid=postdata['id']) & Q(uuid=postdata['uuid'])).update(**postdata2)
    result['data'] = 'ok'
    return JsonResponse(result)


def heartbeat(request):
    postdata, err = parse_json_body(request)
    if err:
        return err
    rid = postdata.get('id', '')
    uuid = postdata.get('uuid', '')
    client_ip = get_client_ip(request)
    # Autodiscover: register device on heartbeat if sysinfo has not run yet (client must call this API).
    if rid and uuid:
        device = RustDesDevice.objects.filter(Q(rid=rid) & Q(uuid=uuid)).first()
        if not device:
            device = RustDesDevice(
                rid=rid,
                uuid=uuid,
                cpu='',
                hostname='Pending',
                memory='',
                os='',
                username='',
                version='',
                ip_address=client_ip,
            )
            device.save()
        else:
            device.ip_address = client_ip
            device.save()
    # Refresh token: stamp with *now* so login's age check works. (Stamping a
    # future time made `now - create_time` negative and tokens never expired.)
    if rid and uuid:
        RustDeskToken.objects.filter(Q(rid=rid) & Q(uuid=uuid)).update(create_time=datetime.datetime.now())
    result = {}
    result['data'] = _('Online')
    return JsonResponse(result)


def audit(request):
    postdata, err = parse_json_body(request)
    if err:
        return err
    audit_type = postdata['action'] if 'action' in postdata else ''
    if audit_type == 'new':
        new_conn_log = ConnLog(
            action=postdata['action'] if 'action' in postdata else '',
            conn_id=postdata['conn_id'] if 'conn_id' in postdata else 0,
            from_ip=postdata['ip'] if 'ip' in postdata else '',
            from_id='',
            rid=postdata['id'] if 'id' in postdata else '',
            conn_start=datetime.datetime.now(),
            session_id=postdata['session_id'] if 'session_id' in postdata else 0,
            uuid=postdata['uuid'] if 'uuid' in postdata else '',
        )
        new_conn_log.save()
    elif audit_type == "close":
        ConnLog.objects.filter(Q(conn_id=postdata['conn_id'])).update(conn_end=datetime.datetime.now())
    elif 'is_file' in postdata:
        print(postdata)
        files = json.loads(postdata['info'])['files']
        filesize = convert_filesize(int(files[0][1]))
        new_file_log = FileLog(
            file=postdata['path'],
            user_id=postdata['peer_id'],
            user_ip=json.loads(postdata['info'])['ip'],
            remote_id=postdata['id'],
            filesize=filesize,
            direction=postdata['type'],
            logged_at=datetime.datetime.now(),
        )
        new_file_log.save()
    else:
        try:
            peer = postdata['peer']
            ConnLog.objects.filter(Q(conn_id=postdata['conn_id'])).update(session_id=postdata['session_id'])
            ConnLog.objects.filter(Q(conn_id=postdata['conn_id'])).update(from_id=peer[0])
        except Exception as e:
            print(postdata, e)

    result = {
        'code': 1,
        'data': 'ok'
    }
    return JsonResponse(result)


def convert_filesize(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


def users(request):
    result = {
        'code': 1,
        'data': _('OK')
    }
    return JsonResponse(result)


def peers(request):
    result = {
        'code': 1,
        'data': 'ok'
    }
    return JsonResponse(result)
