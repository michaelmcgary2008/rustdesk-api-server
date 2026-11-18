import django
if django.__version__.split('.')[0]>='4':
    from django.urls import re_path as url
else:
    from django.conf.urls import  url, include

from api import views
from api import views_oidc

urlpatterns = [
    url(r'^login-options$', views_oidc.login_options),
    url(r'^oidc/auth$', views_oidc.oidc_auth),
    url(r'^oidc/auth-query$', views_oidc.oidc_auth_query),
    url(r'^oidc/callback$', views_oidc.callback),
    url(r'^oidc/web-login$', views_oidc.web_login),
    url(r'^login',views.login),
    url(r'^logout',views.logout),
    url(r'^ab$',views.ab),
    url(r'^ab\/get',views.ab_get),  # x86-sciter client compatibility
    url(r'^users',views.users),
    url(r'^peers',views.peers),
    url(r'^currentUser',views.currentUser),
    url(r'^sysinfo',views.sysinfo),
    url(r'^heartbeat',views.heartbeat),
    #url(r'^register',views.register), 
    url(r'^user_action',views.user_action),
    url(r'^work',views.work),
    url(r'^down_peers$',views.down_peers),
    url(r'^manage_devices',views.manage_devices),
    url(r'^assign_peers',views.assign_peers),
    url(r'^device_inventory',views.device_inventory),
    url(r'^share',views.share),
    url(r'^conn_log',views.conn_log),
    url(r'^file_log',views.file_log),
    url(r'^audit',views.audit),
    ]
