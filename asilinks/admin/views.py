"""
BackOffice viewsets
"""
# Django imports
from django.utils.translation import ugettext_lazy as _
# Rest framework imports
from rest_framework import mixins, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
# Mongo rest framework imports
from rest_framework_mongoengine import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
# Model imports
from .documents import OpenSuggest
from main.documents import Category, KnowField, Test, AcademicOptions, Client, Partner, PartnerSkill
from authentication.documents import Account
from requesting.documents import Request
from payments.documents import Transaction
# Serializer imports
from authentication.serializers import AccountSerializer
from .serializers import (CategorySerializer, KnowFieldSerializer, TestSerializer, 
                          AcademicOptionsSerializer, ClientSerializer, PartnerSerializer, 
                          RequestSerializer, OpenSuggestSerializer, PartnerSkillSerializer,
                          TransactionSerializer, AccountDetailSerializer,
                          LockUserSerializer, TableAccountSerializer)

from .statistics import (get_singular_statistics, get_partners_by_level,
                         get_requests_by_status, get_user_statistics,
                         get_clients_by_commercial_sector, get_statistics_by_category)


# Base class for views
class NoDeleteModelView(mixins.CreateModelMixin,
                        mixins.RetrieveModelMixin,
                        mixins.UpdateModelMixin,
                        mixins.ListModelMixin,
                        viewsets.GenericViewSet):
    """
	Base Model View for BackOffice endpoints
	"""
    permission_classes = (IsAuthenticated, IsAdminUser,)


class CategoryViewSet(NoDeleteModelView):
    """
    ADMINISTRACION DE CATEGORIAS
    """
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.all()


class KnowFieldViewSet(NoDeleteModelView):
    """
    Campos de conocimiento
    """
    serializer_class = KnowFieldSerializer

    def get_queryset(self):
        return KnowField.objects.all()


class TestViewSet(NoDeleteModelView):
    """
    TEST PSICOMETRICO
    """
    serializer_class = TestSerializer

    def get_queryset(self):
        return Test.objects.all()


class AcademicOptionsViewSet(NoDeleteModelView):
    """
    OPCIONES ACADEMICAS
    """
    serializer_class = AcademicOptionsSerializer

    def get_queryset(self):
        return AcademicOptions.objects.all()


class ClientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    DETALLES DE CLIENTES
    """
    serializer_class = ClientSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get_queryset(self):
        return Client.objects.all()


class PartnerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    DETALLES DE PARTNERS
    """
    serializer_class = PartnerSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get_queryset(self):
        return Partner.objects.all()


class PartnerSkillViewSet(NoDeleteModelView):
    """
    DETALLES DE HABILIDADES DE PARTNERS
    """
    serializer_class = PartnerSkillSerializer

    def get_queryset(self):
        return PartnerSkill.objects.all()


class RequestViewSet(viewsets.ReadOnlyModelViewSet):
    """
    DETALLES DE LOS REQUERIMIENTOS
    """
    serializer_class = RequestSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get_queryset(self):
        return Request.objects.all()


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    DETALLES DE TRANSACCIONES
    """
    serializer_class = TransactionSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get_queryset(self):
        return Transaction.objects.all()


class OpenSuggestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OpenSuggestSerializer
    queryset = OpenSuggest.objects.all()
    permission_classes = (IsAuthenticated, IsAdminUser,)


class StatisticsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OpenSuggest.objects.all()
    permission_classes = (IsAuthenticated, IsAdminUser,)

    @action(methods=['get'], detail=False)
    def singular(self, request, *args, **kwargs):
        return Response(get_singular_statistics(),
            status=status.HTTP_200_OK)
    
    @action(methods=['get'], detail=False)
    def partners_by_level(self, request, *args, **kwargs):
        return Response(get_partners_by_level(),
            status=status.HTTP_200_OK)

    @action(methods=['get'], detail=False)
    def requests_by_status(self, request, *args, **kwargs):
        return Response(get_requests_by_status(),
            status=status.HTTP_200_OK)
    
    @action(methods=['get'], detail=False)
    def user_statistics(self, request, *args, **kwargs):
        return Response(get_user_statistics(),
            status=status.HTTP_200_OK)
    
    @action(methods=['get'], detail=False)
    def clients_by_commercial_sector(self, request, *args, **kwargs):
        return Response(get_clients_by_commercial_sector(),
            status=status.HTTP_200_OK)

    @action(methods=['get'], detail=False)
    def statistics_by_category(self, request, *args, **kwargs):
        return Response(get_statistics_by_category(),
            status=status.HTTP_200_OK)


class SelfAccountViewSet(mixins.RetrieveModelMixin, 
    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = AccountSerializer
    queryset = Account.objects.all()
    permission_classes = (IsAuthenticated, IsAdminUser)

    @action(methods=['post'], detail=False)
    def account_detail(self, request, *args, **kwargs):
        serializer = AccountDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = Account.objects.get(email=request.data['email'])
        return Response({
            'list': [
                ['Nombre completo: ', user.get_full_name()],
                ['Correo: ', user.email],
                ['Email de usuario: ', 'Sí' if user.email_confirmed else 'No'],
                ['Email Paypal: ', user.paypal_email if user.paypal_email else 'Sin especificar'],
                ['Fecha de ingreso: ', str(user.date_joined)],
                ['Cumpleaños: ', str(user.birth_date)],
                ['Residencia: ', user.residence.__str__()],
                ['Patrocinador: ', user.sponsor.email],
                ['Tiene cuenta cliente: ', 'Sí' if user.client_profile else 'No'],
                ['Tiene cuenta socio: ', 'Sí' if user.partner_profile else 'No'],
                ['Es administrador: ', 'Sí' if user.is_staff else 'No'],
                ['Último acceso: ', str(user.utc_last_login)],
                ['Género: ', user.gender],
            ],
            'last_login': str(user.utc_last_login)
        })

    @action(methods=['post'], detail=False,
        url_path='lock-user', url_name='lock_user')
    def lock_user(self, request, *args, **kwargs):
        success_message = _('El cambio ha sido exitoso.')

        serializer = LockUserSerializer(data=request.data,
            context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': success_message}, 
            status=status.HTTP_202_ACCEPTED)


class TableAccountViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Account.objects.all()
    serializer_class = TableAccountSerializer
    permission_classes = (IsAuthenticated, IsAdminUser)

