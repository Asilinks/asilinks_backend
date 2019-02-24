import datetime as dt

from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework_mongoengine import viewsets
from rest_framework.response import Response
from mongoengine.queryset.visitor import Q

from .documents import Transaction
from .serializers import TransactionSerializer

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = (IsAuthenticated,)
    template_name = 'pdf/financial_report.html'

    def get_queryset(self):
        account = self.request.user
        profile = self.request.query_params.get('profile', 'client')
        date_init = self.request.query_params.get('date_init')
        date_end = self.request.query_params.get('date_end')
        to_pay = []

        if profile == 'client':
            if not date_end:
                to_pay = Transaction.make_debts_to_pay(account.client_profile)
            filter_args = (
                Q(owner=account, operation__in=[Transaction.OP_REQUEST_PAYMENT, Transaction.OP_REFUND]) | \
                Q(receiver=account, operation=Transaction.OP_SPONSOR_FEE), )
            self.filter_kwargs = {}
        elif profile == 'partner':
            filter_args = ()
            self.filter_kwargs = {'owner':account, 'operation': Transaction.OP_PARTNER_SETTLEMENT}
        else:
            raise ValidationError(_('Solo puede seleccionar el profile client o partner.'))

        if date_init:
            try:
                self.filter_kwargs['date__gte'] = dt.datetime.strptime(
                    date_init, settings.REST_FRAMEWORK['DATE_FORMAT']).date()
            except ValueError:
                raise ValidationError({'date_init': _('El formato de fecha es {}'.format(
                    settings.REST_FRAMEWORK['DATE_FORMAT']))})
        else:
            now = dt.date.today()
            self.filter_kwargs['date__gte'] = dt.date(now.year, now.month, 1)

        if date_end:
            try:
                self.filter_kwargs['date__lt'] = dt.datetime.strptime(
                    date_end, settings.REST_FRAMEWORK['DATE_FORMAT']).date()
            except ValueError:
                raise ValidationError({'date_end': _('El formato de fecha es {}'.format(
                    settings.REST_FRAMEWORK['DATE_FORMAT']))})

        return [*to_pay, *Transaction.objects.filter(*filter_args, **self.filter_kwargs)]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)

        if request.query_params.get('format') in ('pdf', ):
            return Response({'data': queryset,
                'date_init': self.filter_kwargs['date__gte'],
                'date_end': self.filter_kwargs.get('date__lt', dt.datetime.now())
            })
        return Response(serializer.data)
