from collections import defaultdict
from operator import itemgetter
import datetime as dt

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from rest_framework import mixins, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_mongoengine import viewsets, generics

# JWT imports
from rest_framework_jwt.views import JSONWebTokenAPIView
from rest_framework_jwt.serializers import JSONWebTokenSerializer
from rest_framework_jwt.settings import api_settings

from asilinks.renderers import JSONMongoRenderer
from asilinks.mixins import (ValidateRecaptchaMixin,
    MessageCreateMixin, SendEmailMixin)

from .documents import *
from .serializers import *
from .utils import save_last_login
from main.permissions import DontHaveProfile, HavePaypalEmail
from fcm.serializers import FCMDeviceSerializer
from fcm.documents import FCMDevice

jwt_response_payload_handler = api_settings.JWT_RESPONSE_PAYLOAD_HANDLER # pylint: disable=invalid-name


class CreateAccountViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def perform_create(self, serializer):
        serializer.save(last_password_change=dt.datetime.utcnow())

    @action(methods=['post'], detail=False)
    def plus_partner(self, request, *args, **kwargs):
        serializer = PartnerAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save(last_password_change=dt.datetime.utcnow())

        return Response(serializer.data, 
            status=status.HTTP_201_CREATED)


class SelfAccountViewSet(mixins.RetrieveModelMixin, 
    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = AccountSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user

    @action(methods=['get', 'patch'], detail=True,
        permission_classes=[IsAuthenticated])
    def legal_docs(self, request, *args, **kwargs):
        instance = self.get_object()

        if request.method == 'GET':
            serializer = LegalDocsSerializer(instance=instance.legal_docs,
                context={'request': self.request})
            return Response(serializer.data)

        elif request.method == 'PATCH':
            serializer = LegalDocsSerializer(instance=instance.legal_docs,
                data=request.data, context={'request': self.request}, partial=True)
            serializer.is_valid(raise_exception=True)
            instance.modify(legal_docs=serializer.save())
            return Response(serializer.data, 
                status=status.HTTP_202_ACCEPTED)

    @action(methods=['get', 'post'], detail=True,
        permission_classes=[IsAuthenticated])
    def devices(self, request, *args, **kwargs):
        instance = self.get_object()

        if request.method == 'GET':
            serializer = FCMDeviceSerializer(instance.devices, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            serializer = FCMDeviceSerializer(data=request.data,
                context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save(owner=instance, date_created=dt.datetime.now())
            return Response(serializer.data, 
            status=status.HTTP_201_CREATED)
    
    @action(methods=['post'], detail=True,
        permission_classes=[IsAuthenticated])
    def delete_device(self, request, *args, **kwargs):
        instance = self.get_object()
        reg_id = request.data.get('registration_id', '')
        instance.devices.filter(registration_id=reg_id).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['post'], detail=True,
        permission_classes=[IsAuthenticated])
    def change_password(self, request, *args, **kwargs):
        success_message = _('La contraseña ha sido cambiada.')

        serializer = ChangePasswordSerializer(data=request.data,
            context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save(None, None)
        return Response({'message': success_message}, 
            status=status.HTTP_202_ACCEPTED)
    
    @action(methods=['post'], detail=True,
        permission_classes=[IsAuthenticated])
    def change_email(self, request, *args, **kwargs):
        success_message = _('Le hemos enviado un correo electrónico.')
        subject_template_name = 'email/email_change_subject.txt'
        email_template_name = 'email/email_change_body_plain.txt'
        html_email_template_name = 'email/email_change_body.html'
        domain_override = settings.EMAIL_REDIRECT_DOMAIN

        serializer = ChangeEmailSerializer(data=request.data,
            context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save(subject_template_name, email_template_name,
            html_email_template_name=html_email_template_name,
            request=request, domain_override=domain_override)
        return Response({'message': success_message},
            status=status.HTTP_202_ACCEPTED)


    @action(methods=['post'], detail=True,
        permission_classes=[IsAuthenticated, DontHaveProfile])
    def make_partner(self, request, *args, **kwargs):
        success_message = _('Bienvenido a la familia Asilinks.')

        serializer = MakePartnerSerializer(data=request.data,
            context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': success_message}, 
            status=status.HTTP_201_CREATED)


class PasswordResetAPIView(MessageCreateMixin, SendEmailMixin, generics.CreateAPIView):
    serializer_class = PasswordResetSerializer
    success_message = _('Le hemos enviado un correo electrónico.')

    subject_template_name = 'email/password_reset_subject.txt'
    email_template_name = 'email/password_reset_body_plain.txt'
    html_email_template_name = 'email/password_reset_body.html'


class PasswordResetConfirmAPIView(MessageCreateMixin, SendEmailMixin, generics.CreateAPIView):
    serializer_class = PasswordResetConfirmSerializer
    success_message = _('La contraseña ha sido cambiada.')

    subject_template_name = 'email/password_confirm_subject.txt'
    email_template_name = 'email/password_confirm_body_plain.txt'
    html_email_template_name = 'email/password_confirm_body.html'


class ChangeEmailConfirmAPIView(MessageCreateMixin, SendEmailMixin, generics.CreateAPIView):
    serializer_class = ChangeEmailConfirmSerializer
    success_message = _('El correo electrónico ha sido cambiado.')

    subject_template_name = 'email/email_confirm_subject.txt'
    email_template_name = 'email/email_confirm_body_plain.txt'
    html_email_template_name = 'email/email_confirm_body.html'


class InviteClientAPIView(MessageCreateMixin, SendEmailMixin, generics.CreateAPIView):
    serializer_class = InviteClientSerializer
    permission_classes = (IsAuthenticated, HavePaypalEmail)
    success_message = _('Tu invitación ha sido enviada.')

    subject_template_name = 'email/invitation_subject.txt'
    email_template_name = 'email/invitation_body_plain.txt'
    html_email_template_name = 'email/invitation_body.html'


class ContactUsAPIView(MessageCreateMixin, generics.CreateAPIView):
    serializer_class = ContactUsSerializer
    success_message = _('Tu comentario ha sido recibido.')


class SuggestUsAPIView(MessageCreateMixin, generics.CreateAPIView):
    serializer_class = SuggestUsSerializer
    permission_classes = (IsAuthenticated,)
    success_message = _('Tu sugerencia ha sido recibida.')


class AuthLoggerViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = AuthLoggerSerializer


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        alpha2_code = self.request.query_params.get('alpha2_code', None)

        if alpha2_code:
            return queryset.filter(alpha2_code=alpha2_code.upper())
        return queryset

    @action(methods=('get', ), detail=False,
            renderer_classes=(JSONMongoRenderer, ))
    def tree_format(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        pipeline = [
            {'$group': { '_id': "$country",
                    'country': {'$first': '$country'}, 
                    'alpha2_code': {'$first': '$alpha2_code'}, 
                    'states': { '$push': {'state':"$state", 'id': '$_id'} }
                    }
            },
            {'$project' : {'_id' : 0}}
        ]

        return Response(queryset.aggregate(*pipeline))

    @action(methods=('get', ), detail=False)
    def countries(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        fields = list()
        items = ('country', 'alpha2_code')
        for country, alpha2_code in list(set(queryset.values_list(*items))):
            fields.append(
                {'country': country, 'alpha2_code': alpha2_code}
            )

        fields.sort(key=itemgetter('country'))
        return Response(fields)


class CustomJSONWebTokenAPIView(JSONWebTokenAPIView):
    """
    Overide JWT Auth view
    """

    # Override post method to include
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            user = serializer.object.get('user') or request.user
            token = serializer.object.get('token')
            response_data = jwt_response_payload_handler(token, user, request)
            response = Response(response_data)

            # Save last login
            save_last_login(user)

            if api_settings.JWT_AUTH_COOKIE:
                expiration = (dt.datetime.utcnow() +
                              api_settings.JWT_EXPIRATION_DELTA)
                response.set_cookie(api_settings.JWT_AUTH_COOKIE,
                                    token,
                                    expires=expiration,
                                    httponly=True)
            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# This view overrides
class CustomObtainJSONWebToken(CustomJSONWebTokenAPIView):
    """
    Set custom serializer class to get JWT token
    """
    serializer_class = type('CustomJSONWebTokenSerializer',
        (ValidateRecaptchaMixin, JSONWebTokenSerializer), {})


# Create custom get token api view
obtain_jwt_token = CustomObtainJSONWebToken.as_view()  # pylint: disable=invalid-name
