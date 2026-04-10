# cython:language_level=3
from django.db import models
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)
from .models_work import *
from django.utils.translation import gettext as _


class MyUserManager(BaseUserManager):
    def create_user(self, username, password=None):
        if not username:
            raise ValueError('Users must have an username')

        user = self.model(username=username,
                          )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password):
        user = self.create_user(username,
                                password=password,

                                )
        user.is_admin = True
        user.save(using=self._db)
        return user


class UserProfile(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(_('Username'),
                                unique=True,
                                max_length=50)

    rid = models.CharField(verbose_name='RustDesk ID', max_length=16)
    uuid = models.CharField(verbose_name='uuid', max_length=60)
    autoLogin = models.BooleanField(verbose_name='autoLogin', default=True)
    rtype = models.CharField(verbose_name='rtype', max_length=20)
    deviceInfo = models.TextField(verbose_name=_('Login info'), blank=True)

    is_active = models.BooleanField(verbose_name=_('Active'), default=True)
    is_admin = models.BooleanField(verbose_name=_('Administrator'), default=False)

    objects = MyUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['password']

    def get_full_name(self):
        return self.username

    def get_short_name(self):
        return self.username

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        return True

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        return True

    @property
    def is_staff(self):
        "Is the user a member of staff?"
        return self.is_admin

    class Meta:

        verbose_name = _("User")
        verbose_name_plural = _("Users")
        permissions = (
            ("view_task", "Can see available tasks"),
            ("change_task_status", "Can change the status of tasks"),
            ("close_task", "Can remove a task by setting its status as closed"),
        )
