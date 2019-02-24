import datetime as dt

from django.utils.translation import ugettext_lazy as _
from rest_framework import permissions

from .documents import Request

__all__ = [
    'ClientPartnerRequestAccess', 'ClientRequestAccess', 'PartnerRequestAccess',
    'RequestInStatusToDo', 'RequestInStatusInProgress', 'RequestInStatusPending',
    'RequestInStatusDone', 'EditionRequestPermission', 'RequestInStatusDelivered',
    'RequestCanBeCanceled', 'RequestReadytoClose', 'RequestReadytoPay',
]

class ClientPartnerRequestAccess(permissions.BasePermission):
    message = _('No estas asociado a este requerimiento.')

    def partner_has_permission(self, account, instance):
        if not account.has_partner_profile():
            return False
        partner_profile = account.partner_profile

        if instance.partner == partner_profile and \
            instance.status > Request.STATUS_TODO:
            return True

        elif instance.round_partners.filter(partner=partner_profile, rejected=False) and \
            instance.status == Request.STATUS_TODO:
            return True

        return False

    def client_has_permission(self, account, instance):
        if instance.client == account.client_profile:
            return True

        return False

    def has_object_permission(self, request, view, instance):
        if self.client_has_permission(request.user, instance) or \
            self.partner_has_permission(request.user, instance):

            return True

        return False


class ClientRequestAccess(ClientPartnerRequestAccess):
    def has_object_permission(self, request, view, instance):
        if self.client_has_permission(request.user, instance):
            return True

        return False


class PartnerRequestAccess(ClientPartnerRequestAccess):
    def has_object_permission(self, request, view, instance):
        if self.partner_has_permission(request.user, instance):
            return True

        return False


class RequestInStatusToDo(permissions.BasePermission):
    message = _('Este requerimiento ha sido atendido.')

    def has_object_permission(self, request, view, instance):
        if instance.status == Request.STATUS_TODO:
            return True

        return False


class RequestInStatusInProgress(permissions.BasePermission):
    message = _('Esta acción no es válida.')

    def has_object_permission(self, request, view, instance):
        if instance.status == Request.STATUS_IN_PROGRESS:
            return True

        return False


class RequestInStatusDelivered(permissions.BasePermission):
    message = _('No se puede procesar su pago.')

    def has_object_permission(self, request, view, instance):
        if instance.status == Request.STATUS_DELIVERED:
            return True

        return False


class RequestInStatusPending(permissions.BasePermission):
    message = _('Esta acción no es valida.')

    def has_object_permission(self, request, view, instance):
        if instance.status == Request.STATUS_PENDING:
            return True

        return False


class RequestReadytoPay(permissions.BasePermission):
    message = _('Este requerimiento no se encuentra listo para ser pagado.')

    def has_object_permission(self, request, view, instance):
        if instance.status in (Request.STATUS_TODO, Request.STATUS_DELIVERED):
            return True

        return False


class RequestReadytoClose(permissions.BasePermission):
    message = _('Este requerimiento no se encuentra listo para ser cerrado.')

    def has_object_permission(self, request, view, instance):
        if instance.status in (Request.STATUS_PENDING, Request.STATUS_UNSATISFIED):
            return True

        return False


class RequestInStatusDone(permissions.BasePermission):
    message = _('Este requerimiento no ha sido culminado.')

    def has_object_permission(self, request, view, instance):
        if instance.status == Request.STATUS_DONE:
            return True

        return False


class EditionRequestPermission(permissions.BasePermission):
    message = _('En este punto no puede editar el requerimiento.')

    def has_object_permission(self, request, view, instance):
        if request.method in ('PATCH', 'PUT', 'DELETE'):
            if instance.status == Request.STATUS_TODO:
                return True
            else:
                return False
        else:
            return True


class RequestCanBeCanceled(permissions.BasePermission):
    message = _('Este requerimiento no puede ser dado de baja.')

    def has_object_permission(self, request, view, instance):
        return instance.can_be_canceled()
