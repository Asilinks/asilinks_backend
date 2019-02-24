# Rest framework imports
from rest_framework.routers import DefaultRouter

# Django imports
from django.conf.urls import url, include

# Own imports
from .views import (CategoryViewSet, KnowFieldViewSet, 
					TestViewSet, AcademicOptionsViewSet, 
					ClientViewSet, PartnerViewSet, RequestViewSet,
          StatisticsViewSet, OpenSuggestViewSet, PartnerSkillViewSet,
					TransactionViewSet, SelfAccountViewSet, TableAccountViewSet)

router = DefaultRouter()
router.register(r'category', CategoryViewSet, base_name='admin-category')
router.register(r'know-field', KnowFieldViewSet, base_name='admin-know-field')
router.register(r'test', TestViewSet, base_name='admin-test')
router.register(r'academic-options', AcademicOptionsViewSet, base_name='admin-academic_options')
router.register(r'client', ClientViewSet, base_name='admin-client')
router.register(r'partner', PartnerViewSet, base_name='admin-partner')
router.register(r'partner-skill', PartnerSkillViewSet, base_name='admin-partner-skill')
router.register(r'transactions', TransactionViewSet, base_name='admin-transactions')
router.register(r'request', RequestViewSet, base_name='admin-request')
router.register(r'open-suggest', OpenSuggestViewSet, base_name='admin-open-suggest')
router.register(r'statistics', StatisticsViewSet, base_name='admin-statistics')
router.register(r'accounts', SelfAccountViewSet, base_name='admin-accounts')
router.register(r'user-table', TableAccountViewSet, base_name='admin-user-table')


urlpatterns = [
	url(r'^admin/', include(router.urls)),
]
