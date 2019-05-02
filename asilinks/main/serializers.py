from urllib.parse import quote
from collections import Counter
import datetime as dt

from django.utils.translation import ugettext as _
from django.conf import settings

from rest_framework.reverse import reverse
from rest_framework.exceptions import ValidationError
from rest_framework import serializers, fields

from mongoengine.queryset.visitor import Q
from rest_framework_mongoengine.serializers import (
    DocumentSerializer, EmbeddedDocumentSerializer)

from asilinks.validators import file_max_size, FileMimetypeValidator
from admin.documents import OpenSuggest
from .documents import (Client, Partner, AcademicOptions, Academic, 
    Test, Category, KnowField, Competence, FavoritePartner, DraftRequest,
    PartnerSkill, ExtraDescription, TestReview)
from authentication.documents import Account
from payments. documents import Transaction
from requesting.documents import Request, Message

from admin.notification import CLIENT_MESSAGES, PARTNER_MESSAGES


class ClientSerializer(DocumentSerializer):
    full_name = fields.ReadOnlyField(source='account.get_full_name')
    residence = serializers.StringRelatedField()

    class Meta:
        model = Client
        fields = ('residence', 'rating', 'last_activity', 'full_name',
            'commercial_sector',)


class SelfClientSerializer(DocumentSerializer):
    first_name = fields.ReadOnlyField(source='account.first_name')
    initials = fields.ReadOnlyField(source='account.get_initials')
    sponsor_level = fields.ReadOnlyField(source='account.sponsor_level')
    last_login = fields.ReadOnlyField(source='account.utc_last_login')
    avatar = serializers.ImageField(source='account.avatar', use_url=True)
    residence = serializers.StringRelatedField()
    requests_counts = serializers.SerializerMethodField()
    earned_money = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = ('residence', 'rating', 'first_name', 'avatar',
            'sponsor_level', 'earned_money', 'requests_counts',
            'commercial_sector', 'initials', 'last_login',)

    def get_requests_counts(self, instance):
        return {
            'todo': len(instance.requests_todo),
            'draft': len(getattr(instance, 'requests_draft', [])),
            'in_progress': len(instance.requests_in_progress),
            'done': len(instance.requests_done),
            'canceled': len(instance.requests_canceled),
        }

    def get_earned_money(self, instance):
        return round(Transaction.objects.filter(
            Q(receiver=instance.account,
              operation=Transaction.OP_SPONSOR_FEE) |
            Q(owner=instance.account,
              operation=Transaction.OP_PARTNER_SETTLEMENT)
            ).sum('amount'), 2)

class CompletedPaymentsSerializer(DocumentSerializer):
    item_ref = fields.ReadOnlyField(source='item.name', default='')
    class Meta:
        model = Transaction
        fields = ('amount', 'date', 'item_ref', )


class PendingPaymentsSerializer(DocumentSerializer):
    item_ref = fields.ReadOnlyField(source='name')
    amount = fields.SerializerMethodField()
    date = fields.DateTimeField(source='date_started')

    class Meta:
        model = Request
        fields = ('amount', 'date', 'item_ref', )

    def get_amount(self, instance):
        return instance.calculate_bill()['to_pay']


class SelfClientStatisticsSerializer(DocumentSerializer):
    partners_involved = serializers.SerializerMethodField()
    accounts_referred = serializers.SerializerMethodField()
    requests_counts = serializers.SerializerMethodField()
    finance = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = ('partners_involved', 'accounts_referred', 'requests_counts', 'finance', )

    def get_partners_involved(self, instance):
        counts = Counter([r.partner.level for r in instance.requests_done])

        return {
            Partner.LEVEL_SILVER: counts.get(Partner.LEVEL_SILVER, 0),
            Partner.LEVEL_GOLD: counts.get(Partner.LEVEL_GOLD, 0),
            Partner.LEVEL_BRONZE: counts.get(Partner.LEVEL_BRONZE, 0),
        }

    def get_accounts_referred(self, instance):
        accounts_referred = Account.objects.filter(
            sponsor=instance.account)

        active = list()
        inactive = list()
        for ac in accounts_referred:
            if ac.client_profile.last_activity > dt.datetime.now() - dt.timedelta(days=30):
                active.append(ac.client_profile)
            else:
                inactive.append(ac.client_profile)

        return {
            'total_count': accounts_referred.count(),
            'active_count': len(active),
            'inactive_count': len(inactive),
            'active': ClientSerializer(active, many=True).data,
            'inactive': ClientSerializer(inactive, many=True).data,
        }

    def get_requests_counts(self, instance):
        threshold = dt.datetime.now() - dt.timedelta(days=30)

        return {
            'disregarded': sum([req.date_created < threshold \
                for req in instance.requests_todo]),
            'in_progress': len(instance.requests_in_progress),
            'done': len(instance.requests_done),
            'canceled': len(instance.requests_canceled),
        }

    def get_finance(self, instance):
        completed_payments = Transaction.objects.filter(
            owner=instance.account, operation__in=Transaction.DEBIT_OPS)

        return {
            'completed_payments': CompletedPaymentsSerializer(
                completed_payments, many=True).data,
            'completed_payments_sum': completed_payments.sum('amount'),
            'pending_payments': PendingPaymentsSerializer(
                instance.requests_in_progress, many=True).data,
            'pending_payments_sum': sum([req.calculate_bill()['to_pay'] \
                for req in instance.requests_in_progress]),
            'referral_earnings_sum': Transaction.objects.filter(receiver=instance.account,
                operation=Transaction.OP_SPONSOR_FEE).sum('amount'),
        }


class SelfPartnerStatisticsSerializer(DocumentSerializer):
    sub_categories_involved = serializers.SerializerMethodField()
    accounts_referred = serializers.SerializerMethodField()
    requests_counts = serializers.SerializerMethodField()
    finance = serializers.SerializerMethodField()

    class Meta:
        model = Partner
        fields = ('sub_categories_involved', 'accounts_referred', 'requests_counts', 'finance', )

    def get_sub_categories_involved(self, instance):
        counts = Counter([know for r in instance.requests_done for know in r.know_fields])

        return {key.sub_category: value for key, value in counts.items()}

    def get_accounts_referred(self, instance):
        accounts_referred = Account.objects.filter(
            sponsor=instance.account)

        active = list()
        inactive = list()
        for ac in accounts_referred:
            if ac.client_profile.last_activity > dt.datetime.now() - dt.timedelta(days=30):
                active.append(ac.client_profile)
            else:
                inactive.append(ac.client_profile)

        return {
            'total_count': accounts_referred.count(),
            'active_count': len(active),
            'inactive_count': len(inactive),
            'active': ClientSerializer(active, many=True).data,
            'inactive': ClientSerializer(inactive, many=True).data,
        }

    def get_requests_counts(self, instance):
        return {
            'in_progress': len(instance.requests_in_progress),
            'done': len(instance.requests_done),
            'rejected': len([req for req in instance.requests_rejected 
                if req.round_partners.get(partner=instance).rejected]),
            'canceled': len(instance.requests_canceled),
        }

    def get_finance(self, instance):
        completed_payments = Transaction.objects.filter(
            owner=instance.account, operation=Transaction.OP_PARTNER_SETTLEMENT)

        return {
            'completed_payments': CompletedPaymentsSerializer(
                completed_payments, many=True).data,
            'completed_payments_sum': completed_payments.sum('amount'),
            'pending_payments': PendingPaymentsSerializer(
                instance.requests_in_progress, many=True).data,
            'pending_payments_sum': sum([req.calculate_bill()['to_pay'] \
                for req in instance.requests_in_progress]),
            'referral_earnings_sum': Transaction.objects.filter(receiver=instance.account,
                operation=Transaction.OP_SPONSOR_FEE).sum('amount'),
        }


class ReviewPartnerSerializer(DocumentSerializer):
    avatar = serializers.ImageField(source='client.account.avatar', use_url=True)
    full_name = fields.ReadOnlyField(source='client.account.get_full_name')
    comments = fields.ReadOnlyField(source='partner_review.comments')
    score = fields.ReadOnlyField(source='partner_review.score')

    class Meta:
        model = Request
        fields = ('full_name', 'avatar', 'comments', 'score', )


class PartnerSerializer(DocumentSerializer):
    full_name = fields.ReadOnlyField(source='account.get_full_name')
    residence = serializers.StringRelatedField()
    know_fields = serializers.StringRelatedField(many=True)
    avatar = serializers.ImageField(source='account.avatar', use_url=True)
    done_requests = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()

    class Meta:
        model = Partner
        fields = ('level', 'rating', 'full_name', 'know_fields', 'academics',
            'residence', 'curricular_abstract', 'avatar', 'experience_years',
            'joined_date', 'done_requests', 'reviews', )
        read_only_fields = ('level', 'rating', 'know_fields', 
            'academics', 'experience_years', 'joined_date')
        depth = 2

    def get_done_requests(self, instance):
        return len(instance.requests_done)

    def get_reviews(self, instance):
        last_reviews = [r for r in instance.requests_done if r.partner_review][-3:]

        return ReviewPartnerSerializer(last_reviews, many=True).data


class AcademicSerializer(EmbeddedDocumentSerializer):
    class Meta:
        model = Academic
        fields = '__all__'
        extra_kwargs = {
            'college': {'required': True},
            'career': {'required': True},
            'speciality': {'required': True},
        }


class SelfPartnerSerializer(DocumentSerializer):
    full_name = fields.ReadOnlyField(source='account.get_full_name')
    last_login = fields.ReadOnlyField(source='account.utc_last_login')
    initials = fields.ReadOnlyField(source='account.get_initials')
    residence = serializers.StringRelatedField()
    academics = AcademicSerializer(required=True, many=True)

    class Meta:
        model = Partner
        fields = ('level', 'rating', 'full_name', 'know_fields', 'academics',
            'residence', 'curricular_abstract', 'initials', 'experience_years', 'last_login')
        read_only_fields = ('level', 'rating', 'residence', )
        extra_kwargs = {
            'know_fields': {'required': True},
            'experience_years': {'required': True},
            'curricular_abstract': {'required': True},
        }

    def validate_academics(self, value):
        serializer = AcademicSerializer(data=value, many=True)
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def update(self, instance, validated_data):
        instance.modify(**validated_data)
        return instance


class AcademicOptionsSerializer(DocumentSerializer):
    class Meta:
        model = AcademicOptions
        exclude = ['id']


class TestSerializer(DocumentSerializer):
    class Meta:
        model = Test
        fields = '__all__'
        read_only_fields = ('id', )


class TestUserSerializer(DocumentSerializer):
    class Meta:
        model = Test
        fields = ('id', 'question', 'answers', )


class KnowFieldSerializer(DocumentSerializer):
    class Meta:
        model = KnowField
        fields = ('id', 'category', 'sub_category', 'about',)
        read_only_fields = ('id', )


class ListCategorySerializer(DocumentSerializer):
    links = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'image', 'about', 'links',)
        extra_kwargs = {
            'image': {'write_only': True},
        }

    def get_links(self, instance):
        request = self.context['request']

        return {
            'url': reverse('category-detail',
                kwargs={
                    'name': instance.name
                }, request=request),
            'image': instance.image.url,
        }

    def create(self, validated_data):
        instance = super().create(validated_data)
        instance.image.save(instance.image.name, instance.image)

        return instance


class CategorySerializer(DocumentSerializer):
    know_fields = KnowFieldSerializer(many=True, read_only=True)
    related_categories = ListCategorySerializer(many=True)
    links = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('name', 'about', 'know_fields', 'links', 'image', 
            'related_categories', )
        extra_kwargs = {
            'image': {'write_only': True},
        }

    @classmethod
    def many_init(cls, *args, **kwargs):
        kwargs['child'] = ListCategorySerializer()
        return serializers.ListSerializer(*args, **kwargs)

    def get_links(self, instance):

        return {
            'image': instance.image.url,
        }

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.image.save(instance.image.name, instance.image)

        return instance


class CategorySuggestionSerializer(serializers.Serializer):
    category = fields.CharField(max_length=50)
    sub_category = fields.CharField(max_length=50)
    category_description = fields.CharField(max_length=200)
    sub_category_description = fields.CharField(max_length=200)
    email = fields.EmailField(required=True)

    def save(self):
        data = self.validated_data.copy()
        OpenSuggest.objects.create(email=data.pop('email'),
            endpoint='resources/categories/suggestion/', content=data)


class PartnerSkillSerializer(DocumentSerializer):
    class Meta:
        model = PartnerSkill
        fields = '__all__'


class CompetenceSerializer(EmbeddedDocumentSerializer):
    class Meta:
        model = Competence
        fields = '__all__'


class LevelUpPartnerSerializer(DocumentSerializer):
    full_name = fields.ReadOnlyField(source='account.get_full_name')
    competencies = CompetenceSerializer(write_only=True, many=True)

    class Meta:
        model = Partner
        fields = ('full_name', 'level', 'competencies', )
        read_only_fields = ('level', )

    def validate(self, data):
        level_tests_map = {Partner.LEVEL_BRONZE: 'IOS', Partner.LEVEL_SILVER: 'IOE'}

        if self.instance.level not in level_tests_map:
            raise ValidationError(_('Aún no califacas para presentar la prueba.'))
        group_test = TestReview.TEST_MAP[self.instance.level]

        if not self.instance.has_levelup_chance:
            raise ValidationError(
                _('Aún no califacas para presentar la prueba.'))

        data['test_review'] = TestReview(group_test=group_test,
            competencies=data.pop('competencies'))

        try:
            data['test_review'].clean()
        except TestReview.CompetenceRepeated:
            raise ValidationError(
                _('Los tests no pueden estar repetidos.'))
        except TestReview.GroupTestError:
            raise ValidationError(
                _('El group_test es erroneo.'))

        return data

    def update(self, instance, validated_data):
        tests_level_map = {'IOS': Partner.LEVEL_SILVER, 'IOE': Partner.LEVEL_GOLD}
        test = validated_data['test_review']

        if test.approve:
            instance.level = tests_level_map[test.group_test]
            instance.levelup_chance = False
            instance.account.send_message(context={'partner': instance},
                **PARTNER_MESSAGES['level_up'])
        instance.tests_review.append(test)
        instance.save()

        return instance


class FavPartnerSerializer(DocumentSerializer):
    full_name = fields.ReadOnlyField(source='account.get_full_name')
    residence = serializers.StringRelatedField()

    class Meta:
        model = Partner
        fields = ('id', 'level', 'rating', 'full_name', 'residence', )


class FavoritePartnerSerializer(EmbeddedDocumentSerializer):
    partner = FavPartnerSerializer(read_only=True)

    class Meta:
        model = FavoritePartner
        fields = '__all__'
        depth = 2


class ExtraDescriptionSerializer(EmbeddedDocumentSerializer):
    class Meta:
        model = ExtraDescription
        fields = '__all__'
        extra_kwargs = {
            'english_level': { 'default': '' },
            'estimated_duration': { 'default': '' },
            'advance_notion': { 'default': '' },
            'skills': { 'default': [] },
        }


class DetailDraftRequestSerializer(EmbeddedDocumentSerializer):
    english_level = fields.CharField(write_only=True, required=False)
    estimated_duration = fields.CharField(write_only=True, required=False)
    advance_notion = fields.CharField(write_only=True, required=False)
    attachment = fields.FileField(max_length=None, use_url=True, 
        required=False, validators=[file_max_size])
    skills = fields.ListField(write_only=True, required=False,
        child=serializers.CharField()
    )

    class Meta:
        model = DraftRequest
        fields = '__all__'
        read_only_fields = ('date', 'extra_description', )
        extra_kwargs = {
            'name': {'required': True},
            'description': {'required': True},
            'know_fields': {'required': True},
        }
        validators = [
            FileMimetypeValidator(options=Message.CONTENT_TYPES,
                field='attachment')
        ]

    def to_representation(self, obj):
        self.fields['know_fields'] = serializers.StringRelatedField(many=True)
        return super().to_representation(obj)

    def validate(self, data):
        extra = ExtraDescriptionSerializer(data=data)
        extra.is_valid(raise_exception=True)

        return data

    def create(self, validated_data):
        extra = ExtraDescriptionSerializer(data=validated_data)
        extra.is_valid()
        [validated_data.pop(key, None) for key in ('estimated_duration',
            'english_level', 'advance_notion', 'skills')]

        date = validated_data['date']
        validated_data['date'] = date.replace(microsecond=date.microsecond // 1000 * 1000)

        instance = super().create(validated_data)

        if instance.attachment:
            instance.attachment.save(instance.attachment.name,
                instance.attachment, save=False)

        instance.extra_description = extra.save()

        return instance

    def update(self, instance, validated_data):

        extra = ExtraDescriptionSerializer(instance.extra_description,
            data=validated_data, partial=True)
        extra.is_valid()

        if validated_data.get('attachment'):
            instance.attachment.delete()
        instance = super().update(instance, validated_data)

        if validated_data.get('attachment'):
            instance.attachment.save(instance.attachment.name,
                instance.attachment, save=False)

        instance.extra_description = extra.save()
        instance.save()
        return instance


class ListDraftRequestSerializer(EmbeddedDocumentSerializer):
    know_fields = serializers.StringRelatedField(many=True)

    class Meta:
        model = DraftRequest
        fields = ('date', 'name', 'know_fields')
