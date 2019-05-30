
import logging
import datetime as dt
from smtplib import SMTPDataError

from django.conf import settings
from django.utils.translation import ugettext as _
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from rest_framework import serializers, fields
from rest_framework.exceptions import ValidationError

from rest_framework_mongoengine.validators import UniqueValidator
from rest_framework_mongoengine.serializers import (
    DocumentSerializer, EmbeddedDocumentSerializer)

from asilinks.mixins import ValidateRecaptchaMixin
from asilinks.validators import file_max_size
from authentication.documents import Account, LegalDocs, Location
from authentication.utils import email_token_generator
from main.documents import Partner, Client, Competence, TestReview
from main.serializers import CompetenceSerializer
from payments.documents import Transaction
from requesting.documents import Message
from admin.documents import OpenSuggest

logger = logging.getLogger(__name__)

def send_mail(subject_template_name, email_template_name,
              context, from_email, to_email, html_email_template_name=None):
    """
    Send a django.core.mail.EmailMultiAlternatives to `to_email`.
    """
    subject = loader.render_to_string(subject_template_name, context)
    # Email subject *must not* contain newlines
    subject = ''.join(subject.splitlines())
    body = loader.render_to_string(email_template_name, context)

    email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
    if html_email_template_name is not None:
        html_email = loader.render_to_string(html_email_template_name, context)
        email_message.attach_alternative(html_email, 'text/html')

    try: 
        email_message.send()
    except SMTPDataError as err:
        logger.error(err)
        logger.info(context)


class SponsorAccountSerializer(DocumentSerializer):
    full_name = fields.ReadOnlyField(source='get_full_name')

    class Meta:
        model = Account
        fields = ('id', 'full_name')


class ResidenceSerializer(DocumentSerializer):
    class Meta:
        model = Location
        exclude = ('id', )


class AccountSerializer(ValidateRecaptchaMixin, DocumentSerializer):
    full_name = fields.ReadOnlyField(source='get_full_name')
    initials = fields.ReadOnlyField(source='get_initials')
    is_partner = fields.ReadOnlyField(source='has_partner_profile')
    sponsor = fields.ReadOnlyField(source='sponsor.get_full_name')
    refer_email = fields.EmailField(write_only=True,
        default=settings.DEFAULT_EMAIL_SPONSOR)
    avatar = fields.ImageField(use_url=True, required=False, 
        default='avatars/default.png', validators=[file_max_size])
    commercial_sector = fields.CharField(max_length=50, required=False)
    birth_date = fields.DateField(required=True)
    email = fields.EmailField(max_length=254, validators=[
        UniqueValidator(
            queryset=Account.objects.all(),
            message=_('Este correo electrónico ya ha sido registrado.'),
        )]
    )

    class Meta:
        model = Account
        fields = ('first_name', 'last_name', 'email', 'residence', 'full_name',
            'sponsor', 'password', 'refer_email', 'is_partner', 'initials',
            'paypal_email', 'avatar', 'birth_date', 'commercial_sector', 'gender', 
            'is_blogger')

        extra_kwargs = {
            'password': {'required': True, 'write_only': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'residence': {'required': True},
        }

    def validate_refer_email(self, value):
        try:
            Account.objects.get(email__iexact=value)
        except Account.DoesNotExist:
            raise ValidationError(
                _('No hay usuario registrado con este correo electrónico.'))

        return value

    def validate_birth_date(self, value):
        min_age = 18
        max_date = dt.date.today()

        try:
            max_date = max_date.replace(year=max_date.year - min_age)
        except ValueError:  # 29th of february and not a leap year
            assert max_date.month == 2 and max_date.day == 29
            max_date = max_date.replace(year=max_date.year - min_age, month=2, day=28)
        max_date

        if value > max_date:
            raise ValidationError(_('Debe ser mayor de 18 años para participar en la plataforma.'))

        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data['sponsor'] = Account.objects.get(email__iexact=validated_data.pop('refer_email'))
        commercial_sector = validated_data.pop('commercial_sector', '')

        instance = Account(**validated_data)
        instance.set_password(password)
        instance.last_password_change = dt.datetime.utcnow()
        instance.save()
        instance.update_sponsor_statistical_summary()

        client_profile = Client.objects.create(account=instance, residence=instance.residence,
            commercial_sector=commercial_sector, last_activity=dt.datetime.now())

        instance.modify(client_profile=client_profile)

        return instance

    def update(self, instance, validated_data):
        instance.paypal_email = validated_data.get('paypal_email', instance.email)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.birth_date = validated_data.get('birth_date', instance.birth_date)
        instance.residence = validated_data.get('residence', instance.residence)
        instance.gender = validated_data.get('gender', instance.gender)
        instance.save()

        if 'avatar' in validated_data:
            name = 'asi-{}.{}'.format(instance.id, validated_data['avatar'].name.split('.')[-1])
            instance.avatar.save(name, validated_data.get('avatar'))

        if validated_data.get('commercial_sector'):
            instance.client_profile.update(
                commercial_sector=validated_data.get('commercial_sector'))

        instance.client_profile.update(residence=instance.residence)
        if instance.has_partner_profile():
            instance.partner_profile.update(residence=instance.residence)

        return instance


class PartnerAccountSerializer(ValidateRecaptchaMixin, DocumentSerializer):
    full_name = fields.ReadOnlyField(source='get_full_name')
    is_partner = fields.ReadOnlyField(source='has_partner_profile')
    sponsor = fields.ReadOnlyField(source='sponsor.get_full_name')
    refer_email = fields.EmailField(write_only=True,
        default=settings.DEFAULT_EMAIL_SPONSOR)
    avatar = fields.ImageField(use_url=True, required=False, 
        default='avatars/default.png', validators=[file_max_size])
    birth_date = fields.DateField(required=True)
    competencies = CompetenceSerializer(write_only=True, many=True)
    commercial_sector = fields.CharField(max_length=50, required=False)

    class Meta:
        model = Account
        depth = 2
        fields = ('id', 'first_name', 'last_name', 'email', 'residence', 'full_name',
            'sponsor', 'password', 'refer_email', 'is_partner', 'competencies',
            'paypal_email', 'birth_date', 'commercial_sector', 'gender', 'avatar', )

        extra_kwargs = {
            'id': {'read_only': True},
            'password': {'required': True, 'write_only': True},
            'first_name': {'required': True, 'write_only': True},
            'last_name': {'required': True, 'write_only': True},
            'email': {'max_length': 254, 'validators':[ UniqueValidator(
                queryset=Account.objects.all(),
                message=_('Este correo electrónico ya ha sido registrado.'),
            ) ]},
            'residence': {'required': True},
        }

    def validate_refer_email(self, value):
        try:
            Account.objects.get(email__iexact=value)
        except Account.DoesNotExist:
            raise ValidationError(
                _('No hay usuario registrado con este correo electrónico.'))

        return value

    def validate_birth_date(self, value):
        min_age = 18
        max_date = dt.date.today()

        try:
            max_date = max_date.replace(year=max_date.year - min_age)
        except ValueError:  # 29th of february and not a leap year
            assert max_date.month == 2 and max_date.day == 29
            max_date = max_date.replace(year=max_date.year - min_age, month=2, day=28)
        max_date

        if value > max_date:
            raise ValidationError(_('Debe ser mayor de 18 años para participar en la plataforma.'))

        return value

    def validate(self, data):
        # competencies = [Competence(**item) for item in value]
        # group_test = {c.test.group_test for c in competencies}
        test_review = TestReview(group_test='BASE', 
            competencies=data.pop('competencies'))

        try:
            test_review.clean()
        except TestReview.CompetenceRepeated:
            raise ValidationError(
                _('Los tests no pueden estar repetidos.'))
        except TestReview.GroupTestError:
            raise ValidationError(
                _('El group_test debe ser BASE.'))

        if not test_review.approve:
            raise ValidationError(
                _('No calificaste, por favor intentalo en 6 meses.'))

        data['tests_review'] = [test_review]
        return data

    def create(self, validated_data):
        tests = validated_data.pop('tests_review')
        password = validated_data.pop('password')
        validated_data['sponsor'] = Account.objects.get(
            email__iexact=validated_data.pop('refer_email'))
        commercial_sector = validated_data.pop('commercial_sector', '')

        instance = Account(**validated_data)
        instance.set_password(password)
        instance.last_password_change = dt.datetime.utcnow()
        instance.save()

        instance.update_sponsor_statistical_summary()

        client_profile = Client.objects.create(account=instance,
            residence=instance.residence, commercial_sector=commercial_sector,
            last_activity=dt.datetime.now())

        partner_profile = Partner.objects.create(account=instance,
            residence=instance.residence, tests_review=tests)

        partner_profile.update_statistical_summary()

        instance.modify(client_profile=client_profile, partner_profile=partner_profile)

        return instance


class MakePartnerSerializer(DocumentSerializer):
    full_name = fields.ReadOnlyField(source='account.get_full_name')
    residence = serializers.StringRelatedField()
    competencies = CompetenceSerializer(write_only=True, many=True)

    class Meta:
        model = Partner
        fields = ('level', 'rating', 'full_name', 'residence', 'competencies',
            'curricular_abstract', 'know_fields', )
        read_only_fields = ('level', 'rating', 'know_fields', 'residence', )

    def validate(self, data):
        test_review = TestReview(group_test='BASE',
            competencies=data.pop('competencies'))

        try:
            test_review.clean()
        except TestReview.CompetenceRepeated:
            raise ValidationError(
                _('Los tests no pueden estar repetidos.'))
        except TestReview.GroupTestError:
            raise ValidationError(
                _('El group_test debe ser BASE.'))

        if not test_review.approve:
            raise ValidationError(
                _('No calificaste, por favor intentalo en 6 meses.'))

        user = None
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user

        data['account'] = user
        data['residence'] = user.residence
        data['tests_review'] = [test_review]

        return data
    
    def create(self, validated_data):
        instance = super().create(validated_data)
        instance.account.modify(partner_profile=instance)
        instance.update_statistical_summary()

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    password = fields.CharField(write_only=True)
    password_2 = fields.CharField(write_only=True)
    prev_password = fields.CharField(write_only=True)

    def validate(self, data):
        user = self.context['request'].user

        if data['password'] != data['password_2']:
            raise ValidationError({'password': _('Los campos de contraseña deben ser iguales.')})
        if not user.check_password(data['prev_password']):
            raise ValidationError({'prev_password': _('La contraseña actual no es correcta.')})
        if user.match_last_passwords(data['password']):
            raise ValidationError({'password_not_allowed': _('La nueva contraseña no puede coincidir con las 5 anteriores.')})

        return data

    def save(self, subject_template_name, email_template_name, domain_override=None,
        use_https=False, token_generator=default_token_generator,
        from_email=None, request=None, html_email_template_name=None,
        extra_email_context=None):

        user = self.context['request'].user
        new_password = self.validated_data['password']

        user.set_password(self.validated_data['password'])
        user.modify(last_password_change=dt.date.today(),
            push__password_history=make_password(new_password))

        context = {
            'email': user.email,
            'user': user,
            'username': user.get_full_name(),
        }
        if extra_email_context is not None:
            context.update(extra_email_context)


class PasswordResetSerializer(serializers.Serializer):
    email = fields.EmailField(required=True, max_length=254)

    def validate_email(self, value):

        try:
            Account.objects.get(email__iexact=value)
        except Account.DoesNotExist:
            raise ValidationError(
                _('No hay usuario registrado con este correo electrónico.'))

        return value

    def get_users(self, email):
        """Given an email, return matching user(s) who should receive a reset.
        This allows subclasses to more easily customize the default policies
        that prevent inactive users and users with unusable passwords from
        resetting their password.
        """
        active_users = Account.objects.filter(**{'email__iexact': email, 'is_active': True, })
        return active_users

    def save(self, subject_template_name, email_template_name, domain_override=None,
        use_https=False, token_generator=default_token_generator,
        from_email=None, request=None, html_email_template_name=None,
        extra_email_context=None):
        """
        Generate a one-use only link for resetting password and send it to the
        user.
        """
        email = self.validated_data["email"]
        for user in self.get_users(email):
            if not domain_override:
                current_site = get_current_site(request)
                site_name = current_site.name
                domain = current_site.domain
            else:
                site_name = domain = domain_override
            context = {
                'email': email,
                'domain': domain,
                'site_name': site_name,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)).decode(),
                'user': user,
                'username': user.get_full_name(),
                'token': token_generator.make_token(user),
                'protocol': 'https' if use_https else 'http',
            }
            if extra_email_context is not None:
                context.update(extra_email_context)

            send_mail(
                subject_template_name, email_template_name, context, from_email,
                email, html_email_template_name=html_email_template_name,
            )


class AccountDetailSerializer(serializers.Serializer):
    email = fields.EmailField(required=True, max_length=254)

    def validate_email(self, value):

        try:
            Account.objects.get(email__iexact=value)
        except Account.DoesNotExist:
            raise ValidationError(
                _('No hay usuario registrado con este correo electrónico.'))

        return value


class LockUserSerializer(serializers.Serializer):
    is_lock = fields.BooleanField(write_only=True)
    email = fields.EmailField(write_only=True)

    def save(self):

        active_user = not self.validated_data['is_lock']
        user_email = self.validated_data['email']
        user = Account.objects.get(email=user_email)

        if user.is_active is not active_user:
            user.is_active = active_user
            user.save()
        else:
            raise ValidationError({'message': _('No se puede aplicar el cambio ya que tiene el estado solicitado.')})



class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = fields.CharField(required=True, write_only=True, max_length=254)
    token = fields.CharField(required=True, write_only=True, max_length=254)
    password = fields.CharField(required=True, write_only=True, max_length=128)
    password_2 = fields.CharField(required=True, write_only=True, max_length=128)

    def validate(self, data):
        self.user = self.get_user(data['uid'])

        if not self.user:
            raise ValidationError({'uid': _('Vuelva a solicitar el reseteo de su contraseña.')})

        if not default_token_generator.check_token(self.user, data['token']):
            raise ValidationError({'token': _('Vuelva a solicitar el reseteo de su contraseña.')})

        if data['password'] != data['password_2']:
            raise ValidationError(
                {'password': _('Los campos de contraseña deben ser iguales.')})

        if self.user.match_last_passwords(data['password']):
            raise ValidationError({'match_last_passwords': _('Por su seguridad no puede usar las últimas 5 contraseñas.')})

        # if data['prev_password'] and not self.user.check_password(data['prev_password']):
        #     raise ValidationError({'prev_password': _('La contraseña actual no es correcta.')})

        return data

    def get_user(self, uidb64):
        try:
            # urlsafe_base64_decode() decodes to bytestring
            uid = urlsafe_base64_decode(uidb64).decode()
            user = Account.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
            user = None
        return user

    def save(self, subject_template_name, email_template_name, domain_override=None,
        use_https=False, token_generator=default_token_generator,
        from_email=None, request=None, html_email_template_name=None,
        extra_email_context=None):

        new_password = self.validated_data['password']
        self.user.set_password(new_password)
        self.user.modify(last_password_change=dt.date.today(),
            push__password_history=make_password(new_password))

        email = self.user.email
        context = {
            'email': email,
            'user': self.user,
        }
        if extra_email_context is not None:
                context.update(extra_email_context)

        send_mail(
            subject_template_name, email_template_name, context, from_email,
            email, html_email_template_name=html_email_template_name,
        )


class ChangeEmailSerializer(serializers.Serializer):
    email = fields.EmailField(required=True, max_length=254)

    def validate_email(self, value):

        if Account.objects.filter(email__iexact=value):
            raise ValidationError(
                _('Ya hay un usuario registrado con este correo electrónico.'))

        return value

    def save(self, subject_template_name, email_template_name, domain_override=None,
             use_https=False, token_generator=email_token_generator,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        """
        Generate a one-use only link for resetting password and send it to the
        user.
        """
        if not domain_override:
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain
        else:
            site_name = domain = domain_override

        email = self.validated_data['email']
        user = self.context['request'].user
        context = {
                'email': email,
                'domain': domain,
                'site_name': site_name,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)).decode(),
                'ref': urlsafe_base64_encode(force_bytes(email)).decode(),
                'token': token_generator.make_token(user),
                'user': user,
                'username': user.get_full_name(),
                'protocol': 'https' if use_https else 'http',
            }
        if extra_email_context is not None:
                context.update(extra_email_context)

        send_mail(
            subject_template_name, email_template_name, context, from_email,
            email, html_email_template_name=html_email_template_name,
        )


class ChangeEmailConfirmSerializer(serializers.Serializer):
    uid = fields.CharField(required=True, write_only=True, max_length=254)
    token = fields.CharField(required=True, write_only=True, max_length=254)
    ref = fields.CharField(required=True, write_only=True, max_length=254)

    def get_user(self, uidb64):
        try:
            # urlsafe_base64_decode() decodes to bytestring
            uid = urlsafe_base64_decode(uidb64).decode()
            user = Account.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
            user = None
        return user

    def validate(self, data):
        self.user = self.get_user(data['uid'])

        if not self.user:
            raise ValidationError({'uid': _('Vuelva a solicitar el reseteo de su correo electrónico.')})

        if not email_token_generator.check_token(self.user, data['token']):
            raise ValidationError({'token': _('Vuelva a solicitar el reseteo de su correo electrónico.')})

        try:
            data['new_email'] = urlsafe_base64_decode(data['ref']).decode()
        except (TypeError, ValueError, OverflowError):
            raise ValidationError({'ref': _('Vuelva a solicitar el reseteo de su correo electrónico.')})

        if Account.objects.filter(email__iexact=data['new_email']):
            raise ValidationError({'ref': _('Este correo electrónico ya se encuentra registrado.')})

        return data

    def save(self, subject_template_name, email_template_name, domain_override=None,
             use_https=False, token_generator=default_token_generator,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        self.user.modify(email=self.validated_data['new_email'])

        email = self.user.email
        context = {
            'email': email,
            'user': self.user,
        }
        if extra_email_context is not None:
                context.update(extra_email_context)

        send_mail(
            subject_template_name, email_template_name, context, from_email,
            email, html_email_template_name=html_email_template_name,
        )


class InviteClientSerializer(serializers.Serializer):
    receiver_name = fields.CharField(required=True, max_length=254)
    email = fields.EmailField(required=True, max_length=254)

    def validate_email(self, value):

        try:
            Account.objects.get(email__iexact=value)
        except Account.DoesNotExist:
            return value

        raise ValidationError(_('Este correo electrónico ya se encuentra registrado.'))

    def save(self, subject_template_name, email_template_name, domain_override=None,
        use_https=False, token_generator=default_token_generator,
        from_email=None, request=None, html_email_template_name=None,
        extra_email_context=None):

        if not domain_override:
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain
        else:
            site_name = domain = domain_override

        email = self.validated_data['email']
        context = {
                'email': email,
                'receiver_name': self.validated_data['receiver_name'],
                'domain': domain,
                'site_name': site_name,
                'user': self.context['request'].user,
                'protocol': 'https' if use_https else 'http',
            }
        if extra_email_context is not None:
                context.update(extra_email_context)

        send_mail(
            subject_template_name, email_template_name, context, from_email,
            email, html_email_template_name=html_email_template_name,
        )


class ContactUsSerializer(serializers.Serializer):
    from_email = fields.EmailField(required=True, max_length=254)
    subject = fields.CharField(required=True, max_length=254)
    message = fields.CharField(required=True, max_length=5000)

    def save(self):
        data = self.validated_data.copy()
        OpenSuggest.objects.create(email=data.pop('from_email'),
            endpoint='contact_us/', content=data)


class SuggestUsSerializer(serializers.Serializer):
    subject = fields.CharField(required=True, max_length=254)
    message = fields.CharField(required=True)

    def save(self):
        account = self.context['request'].user
        OpenSuggest.objects.create(email=account.email, 
            endpoint='suggest_us/', content=self.validated_data)


class LegalDocsSerializer(EmbeddedDocumentSerializer):
    constitutive_date = fields.DateField()

    class Meta:
        model = LegalDocs
        fields = '__all__'
        natural_fields = ('identity_document', 'nationality',
            'professional_reference', )
        juridical_fields = ('company_name', 'company_id', 'record_name',
            'record_number', 'constitutive_doc', 'constitutive_date',
            'constitutive_country', 'legal_representative', 'partners_name', )
        extra_kwargs = {
            'juridical_person': {'default': False},
        }

    def get_field_names(self, declared_fields, info):
        fields = super().get_field_names(declared_fields, info)
        method = self.context['request'].method

        if method == 'GET':
            juridical_person = getattr(self.instance, 'juridical_person', False)
        elif method == 'PATCH':
            juridical_person = self.initial_data.get('juridical_person', False)

        if juridical_person:
            exclude = self.Meta.natural_fields
        else:
            exclude = self.Meta.juridical_fields

        return [*(set(fields) - set(exclude))]


class AuthLoggerSerializer(serializers.Serializer):
    login_or_logout = fields.BooleanField(write_only=True)
    access_type = fields.BooleanField(write_only=True)
    who_did = fields.BooleanField(write_only=True)
    username = fields.CharField(write_only=True)

    def save(self):

        request_data = self.context['request'].data
        log = 'login' if request_data['login_or_logout'] else 'logout'
        access = 'approved' if request_data['access_type'] else 'denied'
        who = 'user' if request_data['who_did'] else 'system'
        user = request_data['username']
        ip = self.context['request'].META['REMOTE_ADDR']
        message = '{} - {} - {} - {} - {}'.format(user, log, access, who, ip)
        logger.info(message)


class LocationSerializer(DocumentSerializer):
    class Meta:
        model = Location
        fields = '__all__'
