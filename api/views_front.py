# cython:language_level=3
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import auth
from api.models import RustDeskPeer, RustDesDevice, UserProfile, ShareLink, ConnLog, FileLog, MachineGroup
from django.forms.models import model_to_dict
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.conf import settings

from itertools import chain
from django.db.models.fields import DateTimeField, DateField, CharField, TextField
import datetime
from django.db.models import Model
import json
import time
import hashlib
import sys

from io import BytesIO
import xlwt
from django.utils.translation import gettext as _

salt = 'xiaomo'
EFFECTIVE_SECONDS = 7200


def getStrMd5(s):
    if not isinstance(s, (str,)):
        s = str(s)

    myHash = hashlib.md5()
    myHash.update(s.encode())

    return myHash.hexdigest()


def model_to_dict2(instance, fields=None, exclude=None, replace=None, default=None):
    """
    :param instance: Model instance (not a queryset).
    :param fields: Optional tuple of field names to include.
    :param exclude: Optional tuple of field names to exclude.
    :param replace: Map database field names to display names.
    :param default: Extra key/value pairs to add.
    """
    if not isinstance(instance, Model):
        raise Exception(_('model_to_dict2 expects a model instance'))
    if replace and type(replace) == dict:   # noqa
        for replace_field in replace.values():
            if hasattr(instance, replace_field):
                raise Exception(_(f'model_to_dict2: target name {replace_field} already exists'))
    if default and type(default) == dict:   # noqa
        for default_key in default.keys():
            if hasattr(instance, default_key):
                raise Exception(_(f'model_to_dict2: default key {default_key} already exists'))  # noqa
    opts = instance._meta
    data = {}
    for f in chain(opts.concrete_fields, opts.private_fields, opts.many_to_many):
        if not getattr(f, 'editable', False):
            if type(f) == DateField or type(f) == DateTimeField:   # noqa
                pass
            else:
                continue
        if fields is not None and f.name not in fields:
            continue
        if exclude and f.name in exclude:
            continue

        key = f.name
        if type(f) == DateTimeField:   # noqa
            value = getattr(instance, key)
            value = datetime.datetime.strftime(value, '%Y-%m-%d %H:%M')
        elif type(f) == DateField:   # noqa
            value = getattr(instance, key)
            value = datetime.datetime.strftime(value, '%Y-%m-%d')
        elif type(f) == CharField or type(f) == TextField:   # noqa
            value = getattr(instance, key)
            try:
                value = json.loads(value)
            except Exception as _:  # noqa
                value = value
        else:
            key = f.name
            value = f.value_from_object(instance)
            # data[f.name] = f.value_from_object(instance)
        if replace and key in replace.keys():
            key = replace.get(key)
        data[key] = value
    if default:
        data.update(default)
    return data


def index(request):
    print('sdf', sys.argv)
    if request.user and request.user.username != 'AnonymousUser':
        return HttpResponseRedirect('/api/work')
    return HttpResponseRedirect('/api/user_action?action=login')


def user_action(request):
    action = request.GET.get('action', '')
    if action == 'login':
        return user_login(request)
    elif action == 'register':
        return user_register(request)
    elif action == 'logout':
        return user_logout(request)
    else:
        return


def user_login(request):
    if request.method == 'GET':
        return render(request, 'login.html')

    username = request.POST.get('account', '')
    password = request.POST.get('password', '')
    if not username or not password:
        return JsonResponse({'code': 0, 'msg': _('Missing username or password.')})

    user = auth.authenticate(username=username, password=password)
    if user:
        auth.login(request, user)
        return JsonResponse({'code': 1, 'url': '/api/work'})
    else:
        return JsonResponse({'code': 0, 'msg': _('Invalid username or password.')})


def user_register(request):
    info = ''
    if request.method == 'GET':
        return render(request, 'reg.html')
    ALLOW_REGISTRATION = settings.ALLOW_REGISTRATION
    result = {
        'code': 0,
        'msg': ''
    }
    if not ALLOW_REGISTRATION:
        result['msg'] = _('Registration is disabled. Contact an administrator.')
        return JsonResponse(result)

    username = request.POST.get('user', '')
    password1 = request.POST.get('pwd', '')

    if len(username) <= 3:
        info = _('Username must be longer than 3 characters.')
        result['msg'] = info
        return JsonResponse(result)

    if len(password1) < 8 or len(password1) > 20:
        info = _('Password must be between 8 and 20 characters.')
        result['msg'] = info
        return JsonResponse(result)

    user = UserProfile.objects.filter(Q(username=username)).first()
    if user:
        info = _('Username already exists.')
        result['msg'] = info
        return JsonResponse(result)
    user = UserProfile(
        username=username,
        password=make_password(password1),
        is_admin=True if UserProfile.objects.count() == 0 else False,
        is_superuser=True if UserProfile.objects.count() == 0 else False,
        is_active=True
    )
    user.save()
    result['msg'] = info
    result['code'] = 1
    return JsonResponse(result)


@login_required(login_url='/api/user_action?action=login')
def user_logout(request):
    # info=''
    auth.logout(request)
    return HttpResponseRedirect('/api/user_action?action=login')


def _truncate_field(s, n):
    s = s or ''
    return s if len(s) <= n else s[: max(0, n - 1)] + '…'


def get_single_info(uid):
    peer_objs = RustDeskPeer.objects.filter(Q(uid=uid)).select_related('machine_group')
    rids = [x.rid for x in peer_objs]
    peers = {}
    for x in peer_objs:
        d = model_to_dict(x)
        d['group_name'] = x.machine_group.name if x.machine_group else ''
        peers[x.rid] = d
    # print(peers)
    devices = RustDesDevice.objects.filter(rid__in=rids)
    devices = {x.rid: x for x in devices}
    now = datetime.datetime.now()
    for rid, device in devices.items():
        peers[rid]['create_time'] = device.create_time.strftime('%Y-%m-%d')
        peers[rid]['update_time'] = device.update_time.strftime('%Y-%m-%d %H:%M')
        peers[rid]['version'] = device.version
        peers[rid]['memory'] = device.memory
        peers[rid]['cpu'] = device.cpu
        peers[rid]['os'] = device.os
        peers[rid]['ip_address'] = device.ip_address or ''
        peers[rid]['is_online'] = (now - device.update_time).total_seconds() <= 120
        peers[rid]['status'] = _('Online') if peers[rid]['is_online'] else _('Offline')

    for rid, p in peers.items():
        if rid not in devices:
            p['is_online'] = False
            p['status'] = _('Offline')
            p.setdefault('update_time', '—')
            p.setdefault('create_time', '')
            p.setdefault('version', '')
            p.setdefault('memory', '')
            p.setdefault('cpu', '')
            p.setdefault('os', '')
            p.setdefault('ip_address', '')

    for rid in peers.keys():
        peers[rid]['has_rhash'] = _('Yes') if len(peers[rid]['rhash']) > 1 else _('No')

    return [v for k, v in peers.items()]


def get_all_info():
    devices_qs = RustDesDevice.objects.all()
    devices = {x.rid: model_to_dict2(x) for x in devices_qs}
    peer_list = RustDeskPeer.objects.select_related('machine_group').all()
    user_ids = []
    for p in peer_list:
        try:
            user_ids.append(int(p.uid))
        except (TypeError, ValueError):
            continue
    users_map = {str(u.id): u.username for u in UserProfile.objects.filter(id__in=user_ids)}
    now = datetime.datetime.now()
    rid_info = {}
    for p in peer_list:
        uname = users_map.get(str(p.uid), _('Not logged in'))
        gname = p.machine_group.name if p.machine_group_id else ''
        if p.rid not in rid_info:
            rid_info[p.rid] = {'users': [], 'groups': set()}
        if uname not in rid_info[p.rid]['users']:
            rid_info[p.rid]['users'].append(uname)
        if gname:
            rid_info[p.rid]['groups'].add(gname)
    for rid, v in devices.items():
        info = rid_info.get(rid)
        if info:
            v['rust_user'] = ', '.join(info['users'])
            v['group_name'] = ', '.join(sorted(info['groups'])) if info['groups'] else ''
        else:
            v['rust_user'] = _('Not logged in')
            v['group_name'] = ''
        try:
            dt = datetime.datetime.strptime(v['update_time'], '%Y-%m-%d %H:%M')
            v['is_online'] = (now - dt).total_seconds() <= 120
            v['status'] = _('Online') if v['is_online'] else _('Offline')
        except Exception:  # noqa
            v['is_online'] = False
            v['status'] = _('Offline')
    return [v for k, v in devices.items()]


@login_required(login_url='/api/user_action?action=login')
def work(request):
    username = request.user
    u = UserProfile.objects.get(username=username)

    show_type = request.GET.get('show_type', '')
    show_all = True if show_type == 'admin' and u.is_admin else False
    paginator = Paginator(get_all_info(), 24) if show_type == 'admin' and u.is_admin else Paginator(get_single_info(u.id), 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'show_work.html', {'u': u, 'show_all': show_all, 'page_obj': page_obj})


@login_required(login_url='/api/user_action?action=login')
def down_peers(request):
    username = request.user
    u = UserProfile.objects.get(username=username)

    if not u.is_admin:
        print(u.is_admin)
        return HttpResponseRedirect('/api/work')

    all_info = get_all_info()
    f = xlwt.Workbook(encoding='utf-8')
    sheet1 = f.add_sheet(_('Device export'), cell_overwrite_ok=True)
    all_fields = [x.name for x in RustDesDevice._meta.get_fields()]
    all_fields.append('rust_user')
    for i, one in enumerate(all_info):
        for j, name in enumerate(all_fields):
            if i == 0:
                sheet1.write(i, j, name)
            sheet1.write(i + 1, j, one.get(name, '-'))

    sio = BytesIO()
    f.save(sio)
    sio.seek(0)
    response = HttpResponse(sio.getvalue(), content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=DeviceInfo.xls'
    response.write(sio.getvalue())
    return response


def check_sharelink_expired(sharelink):
    now = datetime.datetime.now()
    if sharelink.create_time > now:
        return False
    if (now - sharelink.create_time).seconds < 15 * 60:
        return False
    else:
        sharelink.is_expired = True
        sharelink.save()
        return True


@login_required(login_url='/api/user_action?action=login')
def share(request):
    peers = RustDeskPeer.objects.filter(Q(uid=request.user.id))
    sharelinks = ShareLink.objects.filter(Q(uid=request.user.id) & Q(is_used=False) & Q(is_expired=False))

    # Expire share links lazily on access (no background job).
    for sl in sharelinks:
        check_sharelink_expired(sl)
    sharelinks = ShareLink.objects.filter(Q(uid=request.user.id) & Q(is_used=False) & Q(is_expired=False))
    peers = [{'id': ix + 1, 'name': f'{p.rid}|{p.alias}'} for ix, p in enumerate(peers)]
    sharelinks = [{'shash': s.shash, 'is_used': s.is_used, 'is_expired': s.is_expired, 'create_time': s.create_time, 'peers': s.peers} for ix, s in enumerate(sharelinks)]

    if request.method == 'GET':
        url = request.build_absolute_uri()
        if url.endswith('share'):
            return render(request, 'share.html', {'peers': peers, 'sharelinks': sharelinks})
        else:
            shash = url.split('/')[-1]
            sharelink = ShareLink.objects.filter(Q(shash=shash))
            msg = ''
            title = _('Success')
            if not sharelink:
                title = _('Error')
                msg = _('Link %(url)s: share link missing or expired.') % {'url': url}
            else:
                sharelink = sharelink[0]
                if str(request.user.id) == str(sharelink.uid):
                    title = _('Error')
                    msg = _('Link %(url)s: you cannot redeem your own share link.') % {'url': url}
                else:
                    sharelink.is_used = True
                    sharelink.save()
                    peers = sharelink.peers
                    peers = peers.split(',')
                    peers_self_ids = [x.rid for x in RustDeskPeer.objects.filter(Q(uid=request.user.id))]
                    peers_share = RustDeskPeer.objects.filter(Q(rid__in=peers) & Q(uid=sharelink.uid))

                    for peer in peers_share:
                        if peer.rid in peers_self_ids:
                            continue
                        peer_f = RustDeskPeer.objects.filter(Q(rid=peer.rid) & Q(uid=sharelink.uid))
                        if not peer_f:
                            msg += _('%(rid)s already exists, ') % {'rid': peer.rid}
                            continue

                        if len(peer_f) > 1:
                            msg += _('%(rid)s: multiple rows skipped. ') % {'rid': peer.rid}
                            continue
                        peer = peer_f[0]
                        peer.id = None
                        peer.uid = request.user.id
                        peer.save()
                        msg += f'{peer.rid},'

                    msg += _(' Retrieved successfully.')

            return render(request, 'msg.html', {'title': title, 'msg': msg})
    else:
        data = request.POST.get('data', '[]')

        data = json.loads(data)
        if not data:
            return JsonResponse({'code': 0, 'msg': _('No data.')})
        rustdesk_ids = [x['title'].split('|')[0] for x in data]
        rustdesk_ids = ','.join(rustdesk_ids)
        sharelink = ShareLink(
            uid=request.user.id,
            shash=getStrMd5(str(time.time()) + salt),
            peers=rustdesk_ids,
        )
        sharelink.save()

        return JsonResponse({'code': 1, 'shash': sharelink.shash})


def get_conn_log():
    logs = ConnLog.objects.all()
    logs = {x.id: model_to_dict(x) for x in logs}

    for k, v in logs.items():
        try:
            peer = RustDeskPeer.objects.get(rid=v['rid'])
            logs[k]['alias'] = peer.alias
        except: # noqa
            logs[k]['alias'] = _('UNKNOWN')
        try:
            peer = RustDeskPeer.objects.get(rid=v['from_id'])
            logs[k]['from_alias'] = peer.alias
        except: # noqa
            logs[k]['from_alias'] = _('UNKNOWN')
        # from_zone = tz.tzutc()
        # to_zone = tz.tzlocal()
        # utc = logs[k]['logged_at']
        # utc = utc.replace(tzinfo=from_zone)
        # logs[k]['logged_at'] = utc.astimezone(to_zone)
        try:
            duration = round((logs[k]['conn_end'] - logs[k]['conn_start']).total_seconds())
            m, s = divmod(duration, 60)
            h, m = divmod(m, 60)
            # d, h = divmod(h, 24)
            logs[k]['duration'] = f'{h:02d}:{m:02d}:{s:02d}'
        except:   # noqa
            logs[k]['duration'] = -1

    sorted_logs = sorted(logs.items(), key=lambda x: x[1]['conn_start'], reverse=True)
    new_ordered_dict = {}
    for key, alog in sorted_logs:
        new_ordered_dict[key] = alog

    return [v for k, v in new_ordered_dict.items()]


def get_file_log():
    logs = FileLog.objects.all()
    logs = {x.id: model_to_dict(x) for x in logs}

    for k, v in logs.items():
        try:
            peer_remote = RustDeskPeer.objects.get(rid=v['remote_id'])
            logs[k]['remote_alias'] = peer_remote.alias
        except:   # noqa
            logs[k]['remote_alias'] = _('UNKNOWN')
        try:
            peer_user = RustDeskPeer.objects.get(rid=v['user_id'])
            logs[k]['user_alias'] = peer_user.alias
        except:   # noqa
            logs[k]['user_alias'] = _('UNKNOWN')

    sorted_logs = sorted(logs.items(), key=lambda x: x[1]['logged_at'], reverse=True)
    new_ordered_dict = {}
    for key, alog in sorted_logs:
        new_ordered_dict[key] = alog

    return [v for k, v in new_ordered_dict.items()]


def _inventory_for_admin():
    """All discovered devices with assignment summary for the management UI."""
    rows = get_all_info()
    for row in rows:
        row['rid'] = row.get('rid', '')
    rows.sort(key=lambda x: x.get('update_time') or '', reverse=True)
    return rows


@login_required(login_url='/api/user_action?action=login')
def manage_devices(request):
    if not request.user.is_admin:
        return HttpResponseRedirect('/api/work')
    u = UserProfile.objects.get(username=request.user.username)
    users = [{'id': x.id, 'username': x.username} for x in UserProfile.objects.all().order_by('username')]
    groups = [
        {'id': x.id, 'name': x.name, 'user_id': x.user_id}
        for x in MachineGroup.objects.select_related('user').all().order_by('user_id', 'name')
    ]
    devices = _inventory_for_admin()
    return render(
        request,
        'manage_devices.html',
        {
            'u': u,
            'users': users,
            'groups': groups,
            'devices': devices,
            'groups_json': json.dumps(groups),
        },
    )


@login_required(login_url='/api/user_action?action=login')
def assign_peers(request):
    if request.method != 'POST' or not request.user.is_admin:
        return JsonResponse({'code': 0, 'msg': _('Forbidden or invalid method.')})
    try:
        data = json.loads(request.body.decode())
    except Exception:  # noqa
        return JsonResponse({'code': 0, 'msg': _('Invalid JSON.')})
    action = data.get('action', 'assign')
    rids = data.get('rids') or []
    target_uid = data.get('user_id')
    group_id = data.get('group_id')
    new_group_name = (data.get('new_group_name') or '').strip()

    if not rids:
        return JsonResponse({'code': 0, 'msg': _('Select at least one device.')})
    if target_uid is None or str(target_uid) == '':
        return JsonResponse({'code': 0, 'msg': _('Select a target user.')})

    target = UserProfile.objects.filter(id=target_uid).first()
    if not target:
        return JsonResponse({'code': 0, 'msg': _('User does not exist.')})

    if action == 'unassign':
        RustDeskPeer.objects.filter(rid__in=rids, uid=str(target.id)).delete()
        return JsonResponse({'code': 1, 'msg': _('Unassigned.')})

    mg = None
    if new_group_name:
        mg, _ = MachineGroup.objects.get_or_create(user=target, name=new_group_name)
    elif group_id:
        mg = MachineGroup.objects.filter(id=group_id, user_id=target.id).first()
        if not mg:
            return JsonResponse({'code': 0, 'msg': _('Group missing or not owned by this user.')})

    if action == 'exclusive_assign':
        RustDeskPeer.objects.filter(rid__in=rids).delete()

    for rid in rids:
        dev = RustDesDevice.objects.filter(rid=rid).first()
        if not dev:
            continue
        uname = _truncate_field(dev.username, 20) or '-'
        host = _truncate_field(dev.hostname, 30) or '-'
        peer = RustDeskPeer.objects.filter(uid=str(target.id), rid=rid).first()
        if peer:
            peer.username = uname
            peer.hostname = host
            peer.alias = _truncate_field(dev.hostname, 30) or rid[:12]
            peer.machine_group = mg
            peer.save()
        else:
            RustDeskPeer.objects.create(
                uid=str(target.id),
                rid=rid,
                username=uname,
                hostname=host,
                alias=_truncate_field(dev.hostname, 30) or rid[:12],
                platform='',
                tags='',
                rhash='',
                machine_group=mg,
            )

    return JsonResponse({'code': 1, 'msg': _('Saved.')})


@login_required(login_url='/api/user_action?action=login')
def device_inventory(request):
    """JSON list of all discovered devices and assignments (admin session)."""
    if request.method != 'GET':
        return JsonResponse({'code': 0, 'msg': _('GET only.')})
    if not request.user.is_admin:
        return JsonResponse({'code': 0, 'msg': _('Forbidden.')}, status=403)
    return JsonResponse({'code': 1, 'data': _inventory_for_admin()})


@login_required(login_url='/api/user_action?action=login')
def conn_log(request):
    paginator = Paginator(get_conn_log(), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'show_conn_log.html', {'page_obj': page_obj})


@login_required(login_url='/api/user_action?action=login')
def file_log(request):
    paginator = Paginator(get_file_log(), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'show_file_log.html', {'page_obj': page_obj})
