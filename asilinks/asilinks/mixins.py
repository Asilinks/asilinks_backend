
import logging
import requests

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.tokens import default_token_generator

from rest_framework import serializers, fields, status, mixins, exceptions
from rest_framework.response import Response

logger = logging.getLogger(__name__)

class MessageCreateMixin(mixins.CreateModelMixin):
    success_message = None

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({'message': self.success_message}, status=status.HTTP_202_ACCEPTED, headers=headers)


class SendEmailMixin():
    extra_email_context = None
    from_email = settings.DEFAULT_FROM_EMAIL
    subject_template_name = None
    email_template_name = None
    html_email_template_name = None
    # html_email_template_name = 'email/html_password_reset_body.html'
    domain_override = settings.EMAIL_REDIRECT_DOMAIN
    token_generator = default_token_generator

    def perform_create(self, serializer):
        opts = {
            'use_https': self.request.is_secure(),
            'token_generator': self.token_generator,
            'from_email': self.from_email,
            'email_template_name': self.email_template_name,
            'subject_template_name': self.subject_template_name,
            'request': self.request,
            'html_email_template_name': self.html_email_template_name,
            'extra_email_context': self.extra_email_context,
            'domain_override': self.domain_override,
        }

        serializer.save(**opts)


class ActionSerializerMixin():
    '''
    Utility class for get different serializer class by method.
    For example:
    action_serializer_classes = {
        ('list', ): MyModelListViewSerializer,
        ('update', 'create'): MyModelCreateUpdateSerializer
    }
    '''
    action_serializer_classes = None

    def get_serializer_class(self):

        assert self.action_serializer_classes is not None, (
            'Expected view %s should contain action_serializer_classes '
            'to get right serializer class.' %
            (self.__class__.__name__, )
        )
        for actions, serializer_cls in self.action_serializer_classes.items():
            if self.action in actions:
                return serializer_cls

        print('action not soported: ' + self.action)
        raise exceptions.MethodNotAllowed(self.request.method)


class ValidateRecaptchaMixin(serializers.Serializer):
    """
    Validation layer for reCaptcha token in serializer.
    """

    recaptcha = fields.CharField(required=True, write_only=True)

    def get_field_names(self, declared_fields, info):
        fields = super().get_field_names(declared_fields, info)
        fields.append('recaptcha')

        return fields

    def to_internal_value(self, data):
        ret = super().to_internal_value(data)
        ret.pop('recaptcha', None)

        return ret

    def validate_recaptcha(self, value):
        response = requests.post(settings.RECAPTCHA_VERIFY_URL, {
            'secret': settings.RECAPTCHA_SECRET_KEY,
            'response': value,
        })

        if response.status_code != status.HTTP_200_OK:
            logger.error(response.text)
            msg = _('Hubo un error con el servidor de captcha.')
            raise exceptions.ValidationError(msg)

        if not response.json()['success']:
            msg = _('No fue satisfactoria la verificación del captcha.')
            raise exceptions.ValidationError(msg)
