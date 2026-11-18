from django.conf import settings
from django.db import models


class OidcSession(models.Model):
    """One pending "Sign in with Google" attempt.

    RustDesk clients start it via POST /api/oidc/auth and poll
    /api/oidc/auth-query with `code`; the browser comes back from Google to
    /api/oidc/callback carrying `state`. Web logins use the same row (op='web').
    """
    code = models.CharField(max_length=64, unique=True)
    state = models.CharField(max_length=64, unique=True)
    op = models.CharField(max_length=20)
    rid = models.CharField(max_length=60, blank=True)
    uuid = models.CharField(max_length=100, blank=True)
    device_info = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    error = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)


class GoogleIdentity(models.Model):
    """Links a Google Workspace account to a RustDesk user.

    Rows can be pre-created with only `email` to link an existing account;
    `sub` (Google's stable account id) is filled in at first sign-in.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email = models.CharField(max_length=254, unique=True)
    sub = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.email
