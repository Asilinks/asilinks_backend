# Model imports
from .documents import OpenSuggest
from main.documents import Category, KnowField, Test, Competence, AcademicOptions, Client, Partner, PartnerSkill
from authentication.documents import Account
from requesting.documents import Request
from payments.documents import Transaction

# Rest framework imports
from rest_framework import serializers, fields
from rest_framework.exceptions import ValidationError
from rest_framework_mongoengine.serializers import DocumentSerializer


####### ADMINISTRACION DE CATEGORIAS #######
class CategorySerializer(DocumentSerializer):

    class Meta:
        model = Category
        fields = '__all__'


class KnowFieldSerializer(DocumentSerializer):

    class Meta:
        model = KnowField
        fields = '__all__'


####### TEST PSICOMETRICO #######
class TestSerializer(DocumentSerializer):

    class Meta:
        model = Test
        fields = '__all__'


class CompetenceSerializer(DocumentSerializer):

    class Meta:
        model = Competence
        fields = '__all__'


####### ADMINISTRACION ACADEMICOS #######
class AcademicOptionsSerializer(DocumentSerializer):

    class Meta:
        model = AcademicOptions
        fields = '__all__'


####### DETALLES DE USUARIOS #######
class ClientSerializer(DocumentSerializer):

    class Meta:
        model = Client
        fields = '__all__'


class PartnerSerializer(DocumentSerializer):

    class Meta:
        model = Partner
        fields = '__all__'


class PartnerSkillSerializer(DocumentSerializer):

    class Meta:
        model = PartnerSkill
        fields = '__all__'


####### DETALLES DE LOS REQUERIMIENTOS #######
class RequestSerializer(DocumentSerializer):

    class Meta:
        model = Request
        fields = '__all__'


class OpenSuggestSerializer(DocumentSerializer):

    class Meta:
        model = OpenSuggest
        fields = '__all__'


class TransactionSerializer(DocumentSerializer):

    class Meta:
        model = Transaction
        exclude = ('external_reference',)


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


class TableAccountSerializer(DocumentSerializer):
    full_name = fields.ReadOnlyField(source='get_full_name')
    is_partner = fields.ReadOnlyField(source='has_partner_profile')

    class Meta:
        model = Account
        fields = ('full_name', 'email', 'is_partner', 'gender', 'is_staff', 'is_active')
