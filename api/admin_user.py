# cython:language_level=3
from django.contrib import admin
from api import models
from django import forms
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.utils.translation import gettext as _


class UserCreationForm(forms.ModelForm):
    """A form for creating new users. Includes all the required
    fields, plus a repeated password."""
    password1 = forms.CharField(label=_('Password'), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_('Password confirmation'), widget=forms.PasswordInput)

    class Meta:
        model = models.UserProfile
        fields = ('username', 'is_active', 'is_admin')

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_("Passwords do not match."))
        return password2

    def save(self, commit=True):
        user = super(UserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """A form for updating users."""
    password = ReadOnlyPasswordHashField(
        label=_('Password hash'),
        help_text=_('<a href="../password/">Change password</a>.'),
    )

    class Meta:
        model = models.UserProfile
        fields = ('username', 'is_active', 'is_admin')

    def clean_password(self):
        return self.initial["password"]

    def save(self, commit=True):
        user = super(UserChangeForm, self).save(commit=False)
        if commit:
            user.save()
        return user


class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    password = ReadOnlyPasswordHashField(
        label=_('Password hash'),
        help_text=_('<a href="../password/">Change password</a>.'),
    )
    list_display = ('username', 'rid')
    list_filter = ('is_admin', 'is_active')
    fieldsets = (
        (_('Basic information'), {'fields': ('username', 'password', 'is_active', 'is_admin', 'rid', 'uuid', 'deviceInfo',)}),
    )
    readonly_fields = ('rid', 'uuid')
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'is_active', 'is_admin', 'password1', 'password2',)}
         ),
    )

    search_fields = ('username', )
    ordering = ('username',)
    filter_horizontal = ()


admin.site.register(models.UserProfile, UserAdmin)
admin.site.register(models.RustDeskToken, models.RustDeskTokenAdmin)
admin.site.register(models.RustDeskTag, models.RustDeskTagAdmin)
admin.site.register(models.MachineGroup, models.MachineGroupAdmin)
admin.site.register(models.RustDeskPeer, models.RustDeskPeerAdmin)
admin.site.register(models.RustDesDevice, models.RustDesDeviceAdmin)
admin.site.register(models.ShareLink, models.ShareLinkAdmin)
admin.site.register(models.ConnLog, models.ConnLogAdmin)
admin.site.register(models.FileLog, models.FileLogAdmin)
admin.site.unregister(Group)
admin.site.site_header = _('RustDesk web admin')
admin.site.site_title = _('RustDesk')
