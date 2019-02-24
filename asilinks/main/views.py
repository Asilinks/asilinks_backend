import datetime as dt
from collections import defaultdict, Counter

from django.conf import settings
from django.http import Http404
from django.utils.translation import ugettext_lazy as _

from rest_framework import mixins, status, filters
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action

from rest_framework_mongoengine import viewsets, generics
from mongoengine.errors import DoesNotExist

from .documents import (Client, Partner, AcademicOptions, Academic,
    Test, Category, KnowField, Competence, FavoritePartner, PartnerSkill)
from .permissions import HavePartnerProfile
from .serializers import *
from requesting.documents import Request
from requesting.serializers import DetailRequestSerializer

from authentication.documents import Account


class ClientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer


class PartnerViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Partner.objects.all()
    serializer_class = PartnerSerializer


class AcademicOptionsViewSet(viewsets.ModelViewSet):
    queryset = AcademicOptions.objects.all()
    serializer_class = AcademicOptionsSerializer


class TestViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Test.objects.all()
    serializer_class = TestUserSerializer

    def get_queryset(self):
        queryset = Test.objects.all()
        group_test = self.request.query_params.get('group_test', 'BASE')
        return queryset.filter(group_test=group_test)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = 'name'

    def filter_queryset(self, queryset):
        if 'search' in self.request.query_params:
            return queryset.search_text(self.request.query_params['search'])

        enable = self.request.query_params.get('enable', 'false')
        fields = {}

        if enable.lower() == 'true':
            fields['enable'] = True

        return queryset.filter(**fields)

    @action(methods=('post', ), detail=False)
    def suggestion(self, request, *args, **kwargs):
        serializer = CategorySuggestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save()
        return Response({'message': _('Tu sugerencia ha sido recibida.')},
            status=status.HTTP_202_ACCEPTED)


class KnowFieldViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = KnowField.objects.all()
    serializer_class = KnowFieldSerializer

    def filter_queryset(self, queryset):
        categories = self.request.query_params.getlist('category')
        enable = self.request.query_params.get('enable', 'false')
        fields = {}

        if enable.lower() == 'true':
            fields['enable'] = True
        if categories:
            fields['category__in'] = categories
        return queryset.filter(**fields)

    @action(methods=('get', ), detail=False)
    def tree_format(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        fields = defaultdict(list)
        items = ('id', 'sub_category', 'about')
        for field in queryset.only('category', *items):
            fields[field.category].append(
                {item: str(getattr(field, item)) for item in items}
            )

        return Response(fields)


class PartnerSkillViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PartnerSkill.objects.all()
    serializer_class = PartnerSkillSerializer

    def filter_queryset(self, queryset):
        know_fields = self.request.query_params.getlist('know_field')

        if know_fields:
            return queryset.filter(know_field__in=know_fields)
        return queryset


class AcademicOptionsUserView(generics.RetrieveAPIView):
    # queryset = AcademicOptions.objects.get()
    serializer_class = AcademicOptionsSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return AcademicOptions.objects.get()


class SelfPartnerViewSet(mixins.RetrieveModelMixin, 
    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated, HavePartnerProfile)
    serializer_class = SelfPartnerSerializer

    def get_object(self):
        return self.request.user.partner_profile

    @action(methods=['get', 'put'], detail=True,
        permission_classes=[IsAuthenticated])
    def know_fields(self, request, *args, **kwargs):
        instance = self.get_object()

        if request.method == 'GET':
            serializer = KnowFieldSerializer(instance.know_fields, many=True)
            return Response(serializer.data)

        elif request.method == 'PUT':
            know_fields = KnowField.objects.filter(id__in=request.data)
            instance.modify(know_fields=know_fields)

            serializer = KnowFieldSerializer(know_fields, many=True)
            return Response(serializer.data, 
            status=status.HTTP_202_ACCEPTED)

    @action(methods=['get', 'put'], detail=True,
        permission_classes=[IsAuthenticated])
    def academics(self, request, *args, **kwargs):
        instance = self.get_object()

        if request.method == 'GET':
            serializer = AcademicSerializer(instance.academics, many=True)
            return Response(serializer.data)

        elif request.method == 'PUT':
            serializer = AcademicSerializer(data=request.data, many=True)
            serializer.is_valid(raise_exception=True)
            instance.modify(academics=serializer.save())
            return Response(serializer.data, 
                status=status.HTTP_202_ACCEPTED)

    @action(methods=['get'], detail=True,
        permission_classes=[IsAuthenticated, HavePartnerProfile])
    def statistics(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = SelfPartnerStatisticsSerializer(instance)
        return Response(serializer.data)

    @action(methods=['post'], detail=True,
        permission_classes=[IsAuthenticated, HavePartnerProfile])
    def levelup(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = LevelUpPartnerSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data,
            status=status.HTTP_202_ACCEPTED)


class SelfClientViewSet(mixins.RetrieveModelMixin, 
    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated, )
    serializer_class = SelfClientSerializer

    def get_object(self):
        return self.request.user.client_profile

    @action(methods=['get'], detail=True,
        permission_classes=[IsAuthenticated])
    def favorite_partners(self, request, *args, **kwargs):
        unique_favorites = list({fav.partner for fav in self.get_object().favorite_partners})

        serializer = FavPartnerSerializer(unique_favorites, many=True)
        return Response(serializer.data)

    @action(methods=['delete'], detail=True,
        permission_classes=[IsAuthenticated],
        url_path='favorite_partners/(?P<partner_id>[-\w]+)')
    def delete_favorite_partner(self, request, partner_id, *args, **kwargs):
        client = self.get_object()

        try:
            partner = Partner.objects.get(id=partner_id)
        except Partner.DoesNotExist:
            raise ValidationError(_('Este socio no se encuentra registrado.'))

        client.modify(pull__favorite_partners__partner=partner)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['get', 'post'], detail=True,
        permission_classes=[IsAuthenticated])
    def draft_requests(self, request, *args, **kwargs):
        client = self.get_object()

        if request.method == 'GET':
            serializer = ListDraftRequestSerializer(
                client.requests_draft, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            serializer = DetailDraftRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            draft = serializer.save(date=dt.datetime.now())
            client.modify(push__requests_draft=draft)

            return Response(serializer.data, status.HTTP_201_CREATED)

    @action(methods=['get', 'delete', 'patch'], detail=True,
        permission_classes=[IsAuthenticated],
        url_path=r'draft_requests/(?P<draft_date>[\d.]+)')
    def detail_draft_request(self, request, draft_date, *args, **kwargs):
        client = self.get_object()

        try:
            draft_date = dt.datetime.fromtimestamp(float(draft_date))
            draft = client.requests_draft.get(date=draft_date)

        except ValueError:
            return Response(status=status.HTTP_406_NOT_ACCEPTABLE)
        except DoesNotExist:
            raise Http404

        if request.method == 'DELETE':
            draft.attachment.delete()
            client.modify(pull__requests_draft__date=draft_date)
            return Response(status=status.HTTP_204_NO_CONTENT)

        elif request.method == 'GET':
            serializer = DetailDraftRequestSerializer(draft)

        elif request.method == 'PATCH':
            serializer = DetailDraftRequestSerializer(draft, 
                data=request.data, partial=True)

            serializer.is_valid(raise_exception=True)
            serializer.save()

        return Response(serializer.data)

    @action(methods=['post'], detail=True,
        permission_classes=[IsAuthenticated],
            url_path=r'draft_requests/(?P<draft_date>[\d.]+)/publish')
    def publish_draft_request(self, request, draft_date, *args, **kwargs):
        client = self.get_object()

        try:
            draft_date = dt.datetime.fromtimestamp(float(draft_date))
            draft = client.requests_draft.get(date=draft_date)

        except ValueError:
            return Response(status=status.HTTP_406_NOT_ACCEPTABLE)
        except DoesNotExist:
            raise Http404

        serializer = DetailDraftRequestSerializer(draft, 
            data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        draft = serializer.save()

        r = Request.create_from_draft(draft, client)

        return Response(DetailRequestSerializer(r,
            context={'request': request}).data)

    @action(methods=['get'], detail=True,
        permission_classes=[IsAuthenticated])
    def statistics(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = SelfClientStatisticsSerializer(instance)
        return Response(serializer.data)


class PaymentConstantsView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        return Response(settings.PAYMENT_CONSTANTS)
