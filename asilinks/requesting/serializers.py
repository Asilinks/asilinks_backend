from urllib.parse import quote
import datetime as dt
import functools

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from rest_framework.reverse import reverse
from rest_framework.exceptions import ValidationError
from rest_framework import serializers, fields

from rest_framework_mongoengine.serializers import (
    DocumentSerializer, EmbeddedDocumentSerializer)

from asilinks.validators import file_max_size, FileMimetypeValidator
from .documents import (Request, RoundPartner, Message,
    TimeExtension, Review)
from .tasks import select_round_partners
from authentication.documents import Account
from main.documents import Client, Partner
from main.serializers import ExtraDescriptionSerializer
from payments.documents import Transaction, Bill
from payments.interfaces import get_interface, ContextInterfaceError

from admin.notification import CLIENT_MESSAGES, PARTNER_MESSAGES

__all__ = [
    'MakeRequestSerializer', 'MessageSerializer', 'ClientSerializer',
    'OfferPartnerSerializer', 'DetailRequestSerializer', 'ListRequestSerializer',
    'PartnerSerializer', 'RoundPartnerSerializer', 'ReviewRequestSerializer',
    'OfferSerializer', 'TimeExtensionSerializer', 'SendMessageSerializer',
    'PaymentTokenSerializer', 'RejectRequestSerializer',
    'CancelRequestSerializer', 'AcceptOfferSerializer', 'SubmitRequestSerializer',
    'ReceiveRequestSerializer', 'UnsatisfiedRequestSerializer', 'CloseRequestSerializer',
    'RequestStatisticsSerializer',
]


class MessageListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        merged_data = []

        for item in data.filter(reference_ts=None):
            rep = self.child.to_representation(item)

            try:
                rep['response'] = self.child.to_representation(
                    data.get(reference_ts=item.ts))
            except:
                rep['response'] = None

            merged_data.append(rep)

        return merged_data


class MessageSerializer(EmbeddedDocumentSerializer):
    type = fields.ChoiceField(choices=Message.TYPE_CHOICES,
        default=Message.TYPE_TEXT, write_only=True, required=False)
    attachment = fields.FileField(max_length=None, use_url=True,
        required=False, validators=[file_max_size])
    type_display = serializers.SerializerMethodField()
    is_your = serializers.SerializerMethodField()
    is_client = serializers.SerializerMethodField()
    owner = serializers.SlugRelatedField(
        slug_field='first_name', read_only=True)

    class Meta:
        model = Message
        list_serializer_class = MessageListSerializer
        fields = ('content', 'owner', 'ts', 'content', 'type', 'type_display',
            'attachment', 'last_delivery', 'is_your', 'is_client', )
        extra_kwargs = {
            'last_delivery': {'default': False},
        }
        validators = [
            FileMimetypeValidator(options=Message.CONTENT_TYPES,
                field='attachment', mimetype_field='type')
        ]

    def get_type_display(self, obj):
        return obj.get_type_display()

    def get_is_your(self, obj):
        return obj.owner == self.context['request'].user

    def get_is_client(self, obj):
        return obj.owner == self.parent.parent.instance.client.account

    def validate(self, data):

        if data['type'] == Message.TYPE_TEXT:
            data.pop('attachment', None)

            if not data.get('content'):
                raise ValidationError(
                    {'content': _('El mensaje no tiene contenido.')}
                )

        else:
            # data.pop('content', None)
            attachment = data.get('attachment')

            if not attachment:
                raise ValidationError(
                    {'attachment': _('El mensaje no tiene archivo adjunto.')}
                )

        return data


class ClientSerializer(DocumentSerializer):
    full_name = fields.ReadOnlyField(source='account.get_full_name')

    class Meta:
        model = Client
        fields = ('id', 'rating', 'full_name', )


class PartnerSerializer(DocumentSerializer):
    full_name = fields.ReadOnlyField(source='account.get_full_name')
    residence = serializers.StringRelatedField(source='account.residence')

    class Meta:
        model = Partner
        fields = ('id', 'level', 'rating', 'full_name', 'residence')


class ListRoundPartnerSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        # oculta los round partners que no han publicado oferta
        return super().to_representation(data.exclude(price=None))


class RoundPartnerSerializer(EmbeddedDocumentSerializer):
    partner = PartnerSerializer()
    links = serializers.SerializerMethodField()
    new = serializers.SerializerMethodField()

    class Meta:
        model = RoundPartner
        list_serializer_class = ListRoundPartnerSerializer
        fields = ('partner', 'links', 'last_read', 'price', 'new',
            'description', 'duration', 'requisites', )

    def get_links(self, instance):
        request = self.context['request']
        # view = self.context['view']

        return {
            'self': reverse('partner-detail',
                kwargs={'id': instance.partner.id}, request=request),
        }

    def get_new(self, instance):
        parent = self.context['view'].get_object()

        return instance.date_response > parent.last_read_client


class OfferPartnerSerializer(EmbeddedDocumentSerializer):

    class Meta:
        model = RoundPartner
        fields = '__all__'


class MakeRequestSerializer(DocumentSerializer):
    english_level = fields.CharField(write_only=True, required=False)
    estimated_duration = fields.CharField(write_only=True, required=False)
    advance_notion = fields.CharField(write_only=True, required=False)
    attachment = fields.FileField(max_length=None, use_url=True,
        required=False, write_only=True, validators=[file_max_size])
    skills = fields.ListField(write_only=True, required=False,
        child=serializers.CharField()
    )

    round_partners = RoundPartnerSerializer(many=True, read_only=True)
    partner = PartnerSerializer(read_only=True)

    questions = MessageSerializer(many=True, read_only=True)
    com_channel = MessageSerializer(many=True, read_only=True)
    status_display = serializers.SerializerMethodField()
    new_messages = serializers.SerializerMethodField()
    last_read = serializers.SerializerMethodField()
    new_offers = serializers.ReadOnlyField()

    class Meta:
        model = Request
        fields = ('id', 'name', 'description', 'extra_description', 'know_fields', 'date_created',
            'questions', 'com_channel', 'country_alpha2', 'penalty_discount', 'round_partners',
            'partner', 'partner_review', 'client_review', 'status_display', 'status', 'skills',
            'english_level', 'estimated_duration', 'advance_notion', 'attachment', 'date_promise',
            'new_messages', 'last_read', 'new_offers', )
        read_only_fields = ('id', 'date_created', 'extra_description','penalty_discount',
            'partner_review', 'client_review', 'status', 'date_promise', )
        extra_kwargs = {
            'name': {'required': True},
            'description': {'required': True},
            'know_fields': {'required': True, 'min_length': 1},
        }
        validators = [
            FileMimetypeValidator(options=Message.CONTENT_TYPES,
                field='attachment')
        ]

    def to_representation(self, obj):
        self.fields['know_fields'] = serializers.StringRelatedField(many=True)
        return super().to_representation(obj)

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_new_messages(self, obj):
        account = self.context['request'].user
        return obj.new_messages(account)

    def get_last_read(self, obj):
        account = self.context['request'].user
        return obj.get_last_read(account).strftime('%s.%f')

    def validate(self, data):
        extra = ExtraDescriptionSerializer(data=data)
        extra.is_valid(raise_exception=True)

        return data

    def create(self, validated_data):
        attachment = validated_data.pop('attachment', None)
        extra = ExtraDescriptionSerializer(data=validated_data)
        extra.is_valid()
        [validated_data.pop(key, None) for key in ('estimated_duration',
            'english_level', 'advance_notion', 'skills')]

        instance = super().create(validated_data)
        update = {
            'extra_description':extra.save()
        }

        if attachment:
            _type = Message.TYPE_DOC if attachment.content_type in Message.CONTENT_TYPES[
                Message.TYPE_DOC] else Message.TYPE_IMAGE
            message = Message(ts=dt.datetime.now(), owner=self.context['request'].user,
                attachment=attachment, type=_type)

            message.attachment.save(message.attachment.name, 
                message.attachment, save=False)
            update['push__questions'] = message

        instance.modify(**update)
        instance.client.modify(push__requests_todo=instance, last_activity=dt.datetime.now())
        select_round_partners(str(instance.id))
        # select_round_partners.delay(str(instance.id))

        return instance

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)

        extra = ExtraDescriptionSerializer(instance.extra_description,
            data=validated_data, partial=True)
        extra.is_valid()

        instance.extra_description = extra.save()
        instance.save()

        for rp in instance.round_partners:
            if not rp.rejected:
                rp.partner.account.send_message(context={'request': instance},
                    data={'request_id': str(instance.id), 'profile': 'partner'},
                    **PARTNER_MESSAGES['updated_description_requirement'])
        return instance


class DetailRequestSerializer(DocumentSerializer):
    round_partners = RoundPartnerSerializer(many=True)
    partner = PartnerSerializer()
    client = ClientSerializer()

    know_fields = serializers.StringRelatedField(many=True)
    questions = MessageSerializer(many=True)
    com_channel = MessageSerializer(many=True)

    status_display = serializers.SerializerMethodField()
    your_offer = serializers.SerializerMethodField()
    new_messages = serializers.SerializerMethodField()
    last_read = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    pending_extension = serializers.SerializerMethodField()
    new_offers = serializers.ReadOnlyField()

    class Meta: 
        model = Request
        fields = ('id', 'name', 'know_fields', 'description', 'questions', 'com_channel',
            'client', 'partner', 'round_partners', 'status_display', 'status',
            'date_created', 'date_promise', 'penalty_discount', 'your_offer',
            'partner_review', 'client_review', 'extra_description', 'country_alpha2',
            'new_messages', 'last_read', 'new_offers', 'can_cancel', 'pending_extension', )

    def __init__(self, instance, *args, **kwargs):
        if instance.status < Request.STATUS_PENDING:

            last_delivery = instance.com_channel.filter(last_delivery=True)
            last_delivery.update(content='', attachment=None)

            instance.com_channel = instance.com_channel.exclude(
                last_delivery=True)
            [instance.com_channel.append(item) for item in last_delivery]

        super().__init__(instance, *args, **kwargs)

    def get_field_names(self, declared_fields, info):
        fields = super().get_field_names(declared_fields, info)
        account = self.context['request'].user

        if self.instance.client == account.client_profile:
            fields_to_delete = {'client', 'your_offer'}
        else:
            fields_to_delete = {'partner', 'round_partners', 'new_offers',
                'can_cancel', 'pending_extension'}

        return list(set(fields) - fields_to_delete)

    def get_your_offer(self, obj):
        account = self.context['request'].user

        try:
            round_partner = obj.round_partners.get(partner=account.partner_profile)
        except:
            return None

        if not round_partner.date_response:
            return None

        serializer = OfferPartnerSerializer(round_partner)
        return serializer.data

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_new_messages(self, obj):
        account = self.context['request'].user
        return obj.new_messages(account)

    def get_last_read(self, obj):
        account = self.context['request'].user
        return obj.get_last_read(account).strftime('%s.%f')

    def get_can_cancel(self, obj):
        return obj.can_be_canceled()

    def get_pending_extension(self, obj):
        return any(item.approve is None for item in obj.time_extensions)


class ListRequestSerializer(DocumentSerializer):
    client = serializers.StringRelatedField()
    partner = serializers.StringRelatedField()
    know_fields = serializers.StringRelatedField(many=True)
    status_display = serializers.SerializerMethodField()
    your_offer = serializers.SerializerMethodField()
    offers_count = serializers.SerializerMethodField()
    new_messages = serializers.SerializerMethodField()
    new_offers = serializers.ReadOnlyField()

    class Meta:
        model = Request
        fields = ('id', 'name', 'know_fields', 'client', 'partner',
            'status', 'status_display', 'offers_count', 'your_offer', 
            'date_promise', 'date_created', 'new_messages', 'new_offers', )

    def get_field_names(self, declared_fields, info):
        fields = super().get_field_names(declared_fields, info)
        profile_type = self.context['request'].query_params.get('profile', 'client')

        if 'partner' in profile_type:
            fields_to_delete = {'partner', 'round_partners', 'offers_count', 'new_offers'}
        else:
            fields_to_delete = {'client', 'your_offer'}

        return list(set(fields) - fields_to_delete)

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_your_offer(self, obj):
        account = self.context['request'].user
        round_partner = obj.round_partners.get(partner=account.partner_profile)
        if round_partner.date_response and not round_partner.rejected:
            return True
        return False

    def get_offers_count(self, obj):
        return obj.round_partners.exclude(price=None).count()

    def get_new_messages(self, obj):
        account = self.context['request'].user
        return obj.new_messages(account)


class OfferSerializer(EmbeddedDocumentSerializer):

    class Meta:
        model = RoundPartner
        fields = ('requisites', 'description', 'duration', 'price',
            'date_response', 'last_activity')
        extra_kwargs = {
            'description': {'required': True},
            'price': {'required': True, 'min_value': 20, "error_messages":
                {"min_value": "El costo de la propuesta debe ser mayor o igual a 20."}},
            'date_response': {'read_only': True},
            'last_activity': {'read_only': True},
        }


class TimeExtensionSerializer(EmbeddedDocumentSerializer):

    class Meta:
        model = TimeExtension
        fields = ('duration', 'excuse', 'approve', 
            'date_created', 'date_closed')
        read_only_fields = ('date_created', 'date_closed', )

    def validate(self, data):
        now = dt.datetime.now()
        owner = self.context['request'].user

        if owner.partner_profile == self.instance.partner:
            if self.instance.time_extensions.count() >= 2:
                raise ValidationError({
                    'message':_('La prórroga solicitada no procede.')})

            if not 'duration' in data or not 'excuse' in data:
                raise ValidationError({
                    'duration': self.error_messages['required'],
                    'excuse': self.error_messages['required'],
                })

            if self.instance.date_promise < now + dt.timedelta(hours=48):
                raise ValidationError({
                    'message':_("Se ha vencido el plazo para solicitar extensiones de tiempo.")})

            duration = self.instance.round_partners.get(partner=self.instance.partner).duration
            if data['duration'] > duration / 2:
                raise ValidationError({
                    'message': _('No puede solicitar mas tiempo que la mitad de la duración de su propuesta.'),
                    'max_duration': str(duration / 2)})

            if self.instance.time_extensions.count() == 0:
                return {
                    'duration': data['duration'],
                    'excuse': data['excuse'],
                    'approve': True,
                    'date_created': now,
                    'date_closed': now,
                }
            else:
                return {
                    'duration': data['duration'],
                    'excuse': data['excuse'],
                    'approve': None,
                    'date_created': now,
                }

        elif owner.client_profile == self.instance.client:
            if self.instance.time_extensions.count() >= 2:
                if not 'approve' in data:
                    raise ValidationError({
                        'approve': self.error_messages['required'],
                    })

                if self.instance.time_extensions[-1].approve is None:
                    return {
                        'approve': data['approve'],
                        'date_closed': now,
                    }

            raise ValidationError({
                'message':_('No tiene extensiones de tiempo por aprobar.')})

        else:
            raise ValidationError({'message':_('No está asociado a este requerimiento.')})

    def update(self, instance, validated_data):
        owner = self.context['request'].user

        if owner.partner_profile == self.instance.partner:
            extension = TimeExtension(**validated_data)
            instance.modify(push__time_extensions=extension)

            self.instance.client.account.send_message(context={'request': self.instance},
                data={'request_id': str(self.instance.id), 'profile': 'client'},
                **CLIENT_MESSAGES['extension_requested'])

        else:
            extension = instance.time_extensions[-1]
            extension.approve = validated_data['approve']
            extension.date_closed = validated_data['date_closed']
            instance.modify(pop__time_extensions=1)
            instance.modify(push__time_extensions=extension)

        if extension.approve == True:
            promise = functools.reduce(lambda x,y: x+y, [
                instance.date_started, 
                instance.round_partners.get(partner=instance.partner).duration, 
                *[item.duration for item in instance.time_extensions]
            ])
            instance.modify(date_promise=promise)

            # Send notification telling that the extension was aproved
            self.instance.partner.account.send_message(
                data={'request_id': str(self.instance.id), 'profile': 'partner'},
                **PARTNER_MESSAGES['extension_approved'])
        else:
            # Send notification telling that the extension was rejected
            self.instance.partner.account.send_message(
                data={'request_id': str(self.instance.id), 'profile': 'partner'},
                **PARTNER_MESSAGES['extension_rejected'])

        return extension


class SendMessageSerializer(DocumentSerializer):
    content = fields.CharField(max_length=5000, write_only=True)
    type = fields.ChoiceField(choices=Message.TYPE_CHOICES, 
        default=Message.TYPE_TEXT, write_only=True, required=False)
    attachment = fields.FileField(max_length=None, use_url=True, 
        write_only=True, required=False, validators=[file_max_size])
    last_delivery = fields.BooleanField(write_only=True, default=False)
    reference_ts = fields.FloatField(write_only=True, default=None)

    client = fields.CharField(read_only=True, source='client.account.get_full_name')
    know_fields = serializers.StringRelatedField(read_only=True, many=True)
    questions = MessageSerializer(read_only=True, many=True)
    com_channel = MessageSerializer(read_only=True, many=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = ('client', 'know_fields', 'questions', 'com_channel',
            'status_display', 'content', 'type', 'attachment', 
                  'last_delivery', 'reference_ts', 'status', )
        read_only_fields = ('client', 'know_fields', 'questions',
            'com_channel', 'status_display', 'status', )
        validators = [
            FileMimetypeValidator(options=Message.CONTENT_TYPES,
                field='attachment', mimetype_field='type')
        ]

    def get_status_display(self, instance):
        return instance.get_status_display()

    def validate(self, data):

        if data['reference_ts'] is not None:
            try:
                reference_ts = dt.datetime.fromtimestamp(float(data['reference_ts']))
            except:
                raise ValidationError(_('Debe pasar reference_ts en el formato timestamp.'))

            if not self.instance.questions.filter(ts=reference_ts) and \
                    not self.instance.com_channel.filter(ts=reference_ts):
                raise ValidationError(_('No existe un mensaje con ese reference_ts.'))

            if self.instance.questions.filter(reference_ts=reference_ts) or \
                    self.instance.com_channel.filter(reference_ts=reference_ts):
                raise ValidationError(_('Este mensaje ya ha sido respondido.'))

            data['reference_ts'] = reference_ts

        if data['type'] == Message.TYPE_TEXT:
            data.pop('attachment', None)

            if not data.get('content'):
                raise ValidationError(
                    {'content': _('El mensaje no tiene contenido.')}
                )

        else:
            # data.pop('content', None)
            attachment = data.get('attachment')

            if not attachment:
                raise ValidationError(
                    {'attachment': _('El mensaje no tiene archivo adjunto.')}
                )

        return data

    def update(self, instance, validated_data):
        message = Message(ts=dt.datetime.now(),
            owner=self.context['request'].user, **validated_data)

        if message.type != Message.TYPE_TEXT:
            message.attachment.save(message.attachment.name, 
                message.attachment, save=False)

        if instance.status == Request.STATUS_TODO:
            instance.modify(push__questions=message)
            # Get round partner info if exists
            is_round_partner, round_partner = self.get_round_partner(instance)
            # Update last activity if it is round partner
            if is_round_partner:
                round_partner.last_activity = dt.datetime.now()
                round_partner.save()
            # Send notifications to all round partner but the sender
            notify_round_partners = [rp for rp in instance.round_partners if rp is not round_partner]
            # Send message to each partner
            for rp in notify_round_partners:
                rp.partner.account.send_message(context={'request': instance},
                    data={'request_id': str(instance.id), 'profile': 'partner'},
                    **PARTNER_MESSAGES['have_new_message'])
        else:
            instance.modify(push__com_channel=message)
            # Send message to partner
            instance.partner.account.send_message(context={'request': instance},
                data={'request_id': str(instance.id), 'profile': 'partner'},
                **PARTNER_MESSAGES['have_new_message'])

        # Send message to client
        instance.client.account.send_message(context={'request': instance},
            data={'request_id': str(instance.id), 'profile': 'client'},
            **CLIENT_MESSAGES['have_new_message'])

        return instance

    # Returns True if user is round partner
    def get_round_partner(self, instance):
        # Get round partners
        round_partners = instance.round_partners
        # Check if user is round Partner
        try:
            # Returns round partner index
            round_partner_index = [round_partner.partner.account.paypal_email for round_partner in round_partners].index(self.context['request'].user)
            is_round_partner = True
            round_partner = round_partners[round_partner_index]
        except:
            # If index search throws an exception, 
            is_round_partner = False
            round_partner = None
        # Return if exists and round partner
        return (is_round_partner, round_partner)


class PaymentTokenSerializer(DocumentSerializer):
    payment_token = serializers.SerializerMethodField()
    bill = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    interface = fields.ChoiceField(required=False,
        choices=Transaction.INTERFACE_CHOICES)

    class Meta:
        model = Request
        fields = ('status_display', 'status', 'partner',
            'payment_token', 'bill', 'interface', )
        extra_kwargs = {
            'partner': {'required': False, 'write_only': True},
        }

    def validate(self, data):
        if self.instance.status == Request.STATUS_TODO:
            if data.get('partner') is None:
                raise ValidationError({'partner': self.error_messages['required']})

            round_partner = self.instance.round_partners.get(partner=data.get('partner'))
            if not round_partner.price:
                raise ValidationError(_('El socio seleccionado no ha establecido su propuesta.'))

            return {'round_partner': round_partner, 'interface': data.get('interface', 'bypass')}

        else:
            return {'interface': self.instance.transactions[0].interface}

    def get_bill(self, instance):
        return instance.calculate_bill(
            self.validated_data.get('round_partner'),
            self.validated_data.get('interface'))

    def get_payment_token(self, instance):
        bill = self.get_bill(instance)
        payment_interface = get_interface(
            self.validated_data.get('interface'))
        return payment_interface.generate_token(amount=bill['to_pay'])

    def get_status_display(self, instance):
        return instance.get_status_display()


class RejectRequestSerializer(DocumentSerializer):
    know_fields = serializers.StringRelatedField(read_only=True, many=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = ('id', 'name', 'know_fields', 'status', 'status_display', 'date_created', )
        read_only_fields = ('id', 'name', 'know_fields', 'status', 'date_created', )

    def get_status_display(self, obj):
        return obj.get_status_display()

    def save(self, **kwargs):
        partner = self.context['request'].user.partner_profile
        self.instance.round_partners.filter(partner=partner) \
            .update(rejected=True, date_response=dt.datetime.now())

        partner.modify(pull__requests_todo=self.instance, 
            push__requests_rejected=self.instance)

        ## TODO: pendiente enviar request a otro round partner
        self.instance.save()
        return self.instance

class CancelRequestSerializer(DocumentSerializer):
    know_fields = serializers.StringRelatedField(read_only=True, many=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = ('id', 'name', 'know_fields', 'status', 'status_display', 'date_created', )
        read_only_fields = ('id', 'name', 'know_fields', 'status', 'date_created', )

    def get_status_display(self, obj):
        return obj.get_status_display()

    def save(self, **kwargs):
        self.instance.refund()

        self.instance.partner.modify(pull__requests_in_progress=self.instance,
            push__requests_canceled=self.instance)
        self.instance.client.modify(pull__requests_in_progress=self.instance,
            push__requests_canceled=self.instance, last_activity=dt.datetime.now())
        self.instance.modify(status=Request.STATUS_CANCELED, date_canceled=dt.datetime.now())

        Bill.make_bill(self.instance)

        # Send notification to the partner, client has canceled the request
        self.instance.partner.account.send_message(context={'request': self.instance},
            data={'request_id': str(self.instance.id), 'profile': 'partner'},
            **PARTNER_MESSAGES['client_cancel_request'])

        return self.instance


class AcceptOfferSerializer(DocumentSerializer):
    status_display = serializers.SerializerMethodField()
    know_fields = serializers.StringRelatedField(read_only=True, many=True)

    payment_id = fields.CharField(write_only=True)
    payer_id = fields.CharField(write_only=True)
    interface = fields.ChoiceField(default='bypass',
        choices=Transaction.INTERFACE_CHOICES)

    class Meta:
        model = Request
        fields = ('id', 'name', 'know_fields', 'status', 'status_display', 'date_created',
            'partner', 'payment_id', 'payer_id', 'interface', )
        read_only_fields = ('id', 'name', 'know_fields', 'status', 'date_created', )

    def get_status_display(self, obj):
        return obj.get_status_display()

    def validate(self, data):
        round_partner = self.instance.round_partners.get(partner=data.get('partner'))
        if not round_partner.price:
            raise ValidationError(
                _('El socio seleccionado no ha establecido su propuesta.'))
        bill = self.instance.calculate_bill(round_partner, data.get('interface'))

        try:
            transaction = Transaction.make_transaction(bill['to_pay'], 
                Transaction.OP_REQUEST_PAYMENT, self.context['request'].user, 
                payment_id=data.get('payment_id'), payer_id=data.get('payer_id'),
                interface=data.get('interface'), item=self.instance)

        except ContextInterfaceError as err:
            raise ValidationError({'interface': err})

        now = dt.datetime.now()
        validated_data = {
            'status': Request.STATUS_IN_PROGRESS, 
            'price': round_partner.price,
            'sponsor_percent': bill['sponsor_percent'],
            'partner': round_partner.partner, 
            'date_started': now,
            'date_promise': now + round_partner.duration,
        'transaction': transaction
        }

        return validated_data

    def update(self, instance, validated_data):
        transaction = validated_data.pop('transaction')

        instance = super().update(instance, validated_data)
        instance.modify(push__transactions=transaction)

        instance.client.modify(pull__requests_todo=instance,
            push__requests_in_progress=instance, last_activity=dt.datetime.now())

        for round_partner in instance.round_partners.filter(rejected=False):
            if round_partner.partner == instance.partner:
                round_partner.partner.modify(pull__requests_todo=instance,
                    push__requests_in_progress=instance)
                # Send notification to selected partner
                instance.partner.account.send_message(context={'request': instance},
                    data={'request_id': str(instance.id), 'profile': 'partner'},
                    **PARTNER_MESSAGES['were_selected'])
            else:
                round_partner.partner.modify(pull__requests_todo=instance,
                    push__requests_rejected=instance)
                # Send notification to rejected partner
                round_partner.partner.account.send_message(context={'request': instance},
                    data={'request_id': str(instance.id), 'profile': 'partner'},
                    **PARTNER_MESSAGES['were_rejected'])

        # instance.save()
        return instance


class SubmitRequestSerializer(DocumentSerializer):
    status_display = serializers.SerializerMethodField()
    know_fields = serializers.StringRelatedField(read_only=True, many=True)

    attachment = fields.FileField(max_length=None, use_url=True, required=True,
        write_only=True, validators=[file_max_size])

    class Meta:
        model = Request
        fields = ('id', 'name', 'know_fields', 'status', 'status_display', 'date_created',
            'attachment', )
        read_only_fields = ('id', 'name', 'know_fields', 'status', 'date_created', )
        validators = [
            FileMimetypeValidator(options=Message.CONTENT_TYPES,
                field='attachment')
        ]

    def get_status_display(self, obj):
        return obj.get_status_display()

    def update(self, instance, validated_data):
        attachment = validated_data.pop('attachment', None)
        extra = {}

        if attachment:
            _type = Message.TYPE_DOC if attachment.content_type in Message.CONTENT_TYPES[
                Message.TYPE_DOC] else Message.TYPE_IMAGE
            message = Message(ts=dt.datetime.now(), owner=self.context['request'].user,
                attachment=attachment, type=_type, last_delivery=True,
                content='Recibo del socio.')

            message.attachment.save(message.attachment.name, 
                message.attachment, save=False)
            extra['push__com_channel'] = message

        instance.modify(status=Request.STATUS_DELIVERED, 
            date_delivered=dt.datetime.now(), **extra)
        instance.client.account.send_message(context={'request': instance},
            data={'request_id': str(instance.id), 'profile': 'client'},
            **CLIENT_MESSAGES['request_delivered'])
        return instance


class ReceiveRequestSerializer(DocumentSerializer):
    status_display = serializers.SerializerMethodField()
    know_fields = serializers.StringRelatedField(read_only=True, many=True)

    payment_id = fields.CharField(write_only=True)
    payer_id = fields.CharField(write_only=True)

    class Meta:
        model = Request
        fields = ('id', 'name', 'know_fields', 'status', 'status_display', 'date_created',
            'payment_id', 'payer_id', )
        read_only_fields = ('id', 'name', 'know_fields', 'status', 'date_created', )

    def get_status_display(self, obj):
        return obj.get_status_display()

    def validate(self, data):
        amount = self.instance.calculate_bill()['to_pay']
        ## TODO: Evaluar los descuentos por incumplimiento.

        # Compara en caso de que exista una penalizacion por el 40% restante
        if amount > 0:
            try:
                transaction = Transaction.make_transaction(amount,
                    Transaction.OP_REQUEST_PAYMENT, self.context['request'].user, 
                    payment_id=data.get('payment_id'), payer_id=data.get('payer_id'),
                    interface=self.instance.transactions[0].interface, item=self.instance)
        
            except ContextInterfaceError as err:
                raise ValidationError({'interface': err})
        else:
            transaction = []

        validated_data = {
            'status': Request.STATUS_PENDING,
            'transaction': transaction
        }

        return validated_data

    def update(self, instance, validated_data):
        transaction = validated_data.pop('transaction')

        instance = super().update(instance, validated_data)
        instance.modify(push__transactions=transaction)

        return instance


class UnsatisfiedRequestSerializer(DocumentSerializer):
    status_display = serializers.SerializerMethodField()
    know_fields = serializers.StringRelatedField(read_only=True, many=True)

    cause = fields.CharField(required=True, write_only=True)

    class Meta:
        model = Request
        fields = ('id', 'name', 'know_fields', 'status', 'status_display', 'date_created',
            'cause', )
        read_only_fields = ('id', 'name', 'know_fields', 'status', 'date_created', )

    def get_status_display(self, obj):
        return obj.get_status_display()

    def validate(self, data):

        if self.instance.date_unsatisfied:
            raise ValidationError(
                {'message':_('Ya ha reportado que está insatisfecho.')})

        return data

    def update(self, instance, validated_data):
        time_extension = instance.round_partners.get(
            partner=instance.partner).duration / 4

        message = Message(ts=dt.datetime.now(),
            owner=self.context['request'].user, content=validated_data['cause'])

        instance.modify(status=Request.STATUS_UNSATISFIED,
            date_unsatisfied=dt.datetime.now() + time_extension,
            push__com_channel=message)

        ## TODO: incluir un task que revise periodicamente los insatisfechos para realizar la devolucion

        # Send Message, the request was marked as unsatisfied
        instance.partner.account.send_message(context={'request': instance},
            data={'request_id': str(instance.id), 'profile': 'partner'},
            **PARTNER_MESSAGES['request_unsatisfied'])

        return instance


class CloseRequestSerializer(DocumentSerializer):
    status_display = serializers.SerializerMethodField()
    know_fields = serializers.StringRelatedField(read_only=True, many=True)

    class Meta:
        model = Request
        fields = ('id', 'name', 'know_fields', 'status', 'status_display', 'date_created', )
        read_only_fields = ('id', 'name', 'know_fields', 'status', 'date_created', )

    def get_status_display(self, obj):
        return obj.get_status_display()

    def save(self, **kwargs):
        self.instance.close()

        ## TODO: Enviar correo con la factura de asilinks
        return self.instance


class ReviewRequestSerializer(DocumentSerializer):
    status_display = serializers.SerializerMethodField()
    know_fields = serializers.StringRelatedField(read_only=True, many=True)

    score = serializers.IntegerField(min_value=1, max_value=10, write_only=True, required=True)
    comments = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Request
        fields = ('id', 'name', 'know_fields', 'status', 'status_display', 'date_created',
            'score', 'comments', 'client_review', 'partner_review', )
        read_only_fields = ('id', 'name', 'know_fields', 'status', 'date_created',
            'client_review', 'partner_review', )
        depth = 2

    def get_status_display(self, obj):
        return obj.get_status_display()

    def validate(self, data):
        owner = self.context['request'].user
        if owner.client_profile == self.instance.client:
            if not self.instance.partner_review is None:
                raise ValidationError(
                    {'message':_('Ya ha calificado en este requerimiento.')})

        elif owner.partner_profile == self.instance.partner:
            if not self.instance.client_review is None:
                raise ValidationError(
                    {'message':_('Ya ha calificado en este requerimiento.')})

        else:
            raise ValidationError({'message':_('No está asociado a este requerimiento.')})

        return data

    def update(self, instance, validated_data):
        owner = self.context['request'].user
        review = Review(**validated_data)

        if owner.client_profile == self.instance.client:
            instance.modify(partner_review=review)
            instance.client.update_rating()
            instance.partner.account.send_message(context={'request': instance},
                data={'request_id': str(instance.id), 'profile': 'partner'},
                **PARTNER_MESSAGES['were_qualified'])

        elif owner.partner_profile == self.instance.partner:
            instance.modify(client_review=review)
            instance.partner.update_rating()
            instance.client.account.send_message(context={'request': instance},
                data={'request_id': str(instance.id), 'profile': 'client'},
                **CLIENT_MESSAGES['were_qualified'])

        return instance


class RequestStatisticsSerializer(serializers.Serializer):
    requests_counts = serializers.SerializerMethodField()

    def get_requests_counts(self, instance):
        return {
            'todo': len(instance.requests_todo),
            'draft': len(getattr(instance, 'requests_draft', [])),
            'in_progress': len(instance.requests_in_progress),
            'done': len(instance.requests_done),
            'canceled': len(instance.requests_canceled),
        }
