from .admin_user import *

@admin.register(models.GoogleIdentity)
class GoogleIdentityAdmin(admin.ModelAdmin):
    # Pre-create a row with just user + email to link an existing account to
    # a Google sign-in; Google's account id (sub) is filled in at first login.
    list_display = ('email', 'user', 'last_login', 'created')
    search_fields = ('email', 'user__username')
    readonly_fields = ('sub', 'last_login', 'created')
