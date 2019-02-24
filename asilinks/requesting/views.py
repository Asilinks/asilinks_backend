import datetime as dt
import numpy as np
from functools import reduce
from bson.objectid import ObjectId
from dateutil.relativedelta import relativedelta

from django.utils.translation import ugettext_lazy as _
from django.http import Http404

from rest_framework import mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied, MethodNotAllowed
from rest_framework.decorators import action
from rest_framework.response import Response

from rest_framework_mongoengine.viewsets import GenericViewSet, ModelViewSet
from mongoengine.queryset.visitor import Q

from asilinks.mixins import ActionSerializerMixin

from .documents import Request, RoundPartner
from .serializers import *
from .permissions import *
from main.permissions import HavePaypalEmail
from admin.notification import CLIENT_MESSAGES


class RequestViewSet(ActionSerializerMixin, ModelViewSet):
    queryset = Request.objects.all()
    permission_classes = (IsAuthenticated,
        ClientPartnerRequestAccess, EditionRequestPermission)

    action_serializer_classes = {
        ('create', 'partial_update', 'update', ): MakeRequestSerializer,
        ('list', 'monthly_list', ): ListRequestSerializer,
        ('retrieve', ): DetailRequestSerializer,
        ('payment_token', ): PaymentTokenSerializer,
        ('accept_offer', ): AcceptOfferSerializer,
        ('cancel', ): CancelRequestSerializer,
        ('reject', ): RejectRequestSerializer,
        ('send_message', ): SendMessageSerializer,
        ('time_extension', ): TimeExtensionSerializer,
        ('submit', ): SubmitRequestSerializer,
        ('receive', ): ReceiveRequestSerializer,
        ('unsatisfied', ): UnsatisfiedRequestSerializer,
        ('close', ): CloseRequestSerializer,
        ('review', ): ReviewRequestSerializer,
    }

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        if not ObjectId.is_valid(self.kwargs.get(lookup_url_kwarg)):
            raise Http404

        return super().get_object()

    def get_list_queryset(self):
        profile_type = self.request.query_params.get('profile', 'client')
        status = self.request.query_params.getlist('status', ['todo', 'in_progress'])

        if profile_type == 'client':
            profile = self.request.user.client_profile
        elif profile_type == 'partner':
            if not self.request.user.has_partner_profile():
                raise PermissionDenied(_('No posee perfil de socio.'))
            profile = self.request.user.partner_profile
        else:
            raise PermissionDenied(_('Este perfil no se encuentra disponible.'))

        status_set = set(status) & {'todo', 'in_progress', 'rejected', 'done', 'canceled'}
        return reduce(lambda x, y: x + getattr(profile, 'requests_' + y), status_set, list())

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_list_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        self.get_object().update_last_read(request.user)

        return response

    def perform_create(self, serializer):
        account = self.request.user

        serializer.save(client=account.client_profile,
            date_created=dt.datetime.now())

    def perform_destroy(self, instance):
        instance.client.modify(pull__requests_todo=instance)
        for rp in instance.round_partners:
            rp.partner.modify(pull__requests_todo=instance)

        instance.delete()

    @action(methods=['get'], detail=False, permission_classes=[
        IsAuthenticated, ClientPartnerRequestAccess])
    def monthly_list(self, request, *args, **kwargs):
        today = dt.date.today()
        month = request.query_params.get('month', str(today.month))
        year = request.query_params.get('year', str(today.year))
        profile_type = self.request.query_params.get('profile', 'client')

        if not month.isnumeric() or not year.isnumeric():
            raise ValidationError({'message': 'el mes y el año deben ser numéricos.'})

        filters = {
            'status__in': [Request.STATUS_IN_PROGRESS, Request.STATUS_DELIVERED,
                Request.STATUS_PENDING, Request.STATUS_UNSATISFIED],
        }

        if profile_type == 'client':
            filters['client'] = self.request.user.client_profile
        elif profile_type == 'partner':
            if not self.request.user.has_partner_profile():
                raise PermissionDenied(_('No posee perfil de socio.'))
            filters['partner'] = self.request.user.partner_profile
        else:
            raise PermissionDenied(_('Este perfil no se encuentra disponible.'))

        date_init = dt.datetime(int(year), int(month), 1)
        date_end = date_init + relativedelta(months=1) - relativedelta(days=1)
        queryset = self.get_queryset().filter( Q(**filters) &
            ((Q(date_created__gte=date_init) & Q(date_created__lte=date_end)) | 
            (Q(date_promise__gte=date_init) & Q(date_promise__lte=date_end)))
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['post'], detail=True,
        permission_classes=[IsAuthenticated, ClientPartnerRequestAccess])
    def send_message(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        instance.update_last_read(request.user)

        return Response(serializer.data)

    @action(methods=['post'], detail=True, permission_classes=[
        IsAuthenticated, ClientRequestAccess, RequestCanBeCanceled])
    def cancel(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance)
        # serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @action(methods=['post'], detail=True, permission_classes=[
        IsAuthenticated, PartnerRequestAccess, RequestInStatusToDo])
    def reject(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance)
        # serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_204_NO_CONTENT)

    @action(methods=['post'], detail=True, permission_classes=[
        IsAuthenticated, PartnerRequestAccess, RequestInStatusToDo, HavePaypalEmail])
    def send_offer(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = OfferSerializer(instance.round_partners.get(
            partner=request.user.partner_profile), data=request.data)

        serializer.is_valid(raise_exception=True)

        serializer.save(date_response=dt.datetime.now(), last_activity=dt.datetime.now())
        instance.save()

        instance.client.account.send_message(context={'request': instance},
            data={'request_id': str(instance.id), 'profile': 'client'},
            **CLIENT_MESSAGES['round_partner_made_offer'])

        return Response(serializer.data)

    @action(methods=['get', 'post'], detail=True, permission_classes=[
        IsAuthenticated, ClientRequestAccess, RequestReadytoPay])
    def payment_token(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data)

    @action(methods=['post'], detail=True, permission_classes=[
        IsAuthenticated, ClientRequestAccess, RequestInStatusToDo])
    def accept_offer(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @action(methods=['get', 'post'], detail=True, permission_classes=[
        IsAuthenticated, ClientPartnerRequestAccess, RequestInStatusInProgress])
    def time_extension(self, request, *args, **kwargs):
        instance = self.get_object()

        if request.method == 'GET':
            serializer = self.get_serializer(instance.time_extensions, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            serializer = self.get_serializer(instance, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(serializer.data,
                status.HTTP_202_ACCEPTED)

    @action(methods=['post'], detail=True, permission_classes=[
        IsAuthenticated, PartnerRequestAccess, RequestInStatusInProgress])
    def submit(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data,
            status=status.HTTP_202_ACCEPTED)

    @action(methods=['post'], detail=True, permission_classes=[
        IsAuthenticated, ClientRequestAccess, RequestInStatusDelivered])
    def receive(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, 
            status=status.HTTP_202_ACCEPTED)

    @action(methods=['post'], detail=True, permission_classes=[
        IsAuthenticated, ClientRequestAccess, RequestInStatusPending])
    def unsatisfied(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data,
            status=status.HTTP_202_ACCEPTED)

    @action(methods=['post'], detail=True, permission_classes=[
        IsAuthenticated, ClientRequestAccess, RequestReadytoClose])
    def close(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance)
        serializer.save()

        return Response(serializer.data,
            status=status.HTTP_202_ACCEPTED)

    @action(methods=['post'], detail=True, permission_classes=[
        IsAuthenticated, ClientPartnerRequestAccess, RequestInStatusDone])
    def review(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data,
            status=status.HTTP_202_ACCEPTED)

    @action(methods=['post'], detail=True, permission_classes=[
        IsAuthenticated, ClientRequestAccess])
    def append_favorite(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.append_favorite_partner()

        return Response('OK')

    @action(methods=['get'], detail=False,
        permission_classes=[IsAuthenticated, ])
    def statistics(self, request, *args, **kwargs):
        profile_type = self.request.query_params.get('profile', 'client')

        if profile_type == 'client':
            profile = self.request.user.client_profile
        elif profile_type == 'partner':
            if not self.request.user.has_partner_profile():
                raise PermissionDenied(_('No posee perfil de socio.'))
            profile = self.request.user.partner_profile
        else:
            raise PermissionDenied(_('Este perfil no se encuentra disponible.'))

        serializer = RequestStatisticsSerializer(profile)
        return Response(serializer.data)
