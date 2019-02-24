from django.utils.translation import ugettext_lazy as _
from rest_framework import permissions


class HavePartnerProfile(permissions.BasePermission):
    message = _('No tienes un perfil de socio.')

    def has_permission(self, request, view):
        if request.user.has_partner_profile():
            return True
        return False


class DontHaveProfile(permissions.BasePermission):
    message = _('Ya tienes perfil de socio.')

    def has_permission(self, request, view):
        if request.user.has_partner_profile():
            return False
        return True


class HavePaypalEmail(permissions.BasePermission):
    message = _('Debes registrar un correo de paypal.')

    def has_permission(self, request, view):
        if request.user.paypal_email:
            return True
        return False
