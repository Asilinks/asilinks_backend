
from django.conf.urls import url, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_mongoengine.routers import DefaultRouter
# from rest_framework_jwt.views import obtain_jwt_token

import authentication.views as auth_views
import main.views as main_views
import requesting.views as req_views
import payments.views as pay_views

from asilinks.routers import DetailRouter

users_router = DefaultRouter()

users_router.register(r'create_account', auth_views.CreateAccountViewSet)
users_router.register(r'auth_logger', auth_views.AuthLoggerViewSet, base_name='auth-logger')
users_router.register(r'clients', main_views.ClientViewSet)
users_router.register(r'partners', main_views.PartnerViewSet)
users_router.register(r'requests', req_views.RequestViewSet)
users_router.register(r'transactions', pay_views.TransactionViewSet)

detail_router = DetailRouter()

detail_router.register(r'self', auth_views.SelfAccountViewSet, base_name='self-account')
detail_router.register(r'self/partner', main_views.SelfPartnerViewSet, base_name='self-partner')
detail_router.register(r'self/client', main_views.SelfClientViewSet, base_name='self-client')

resources_router = DefaultRouter()

resources_router.register(r'locations', auth_views.LocationViewSet)
resources_router.register(r'categories', main_views.CategoryViewSet)
resources_router.register(r'know_fields', main_views.KnowFieldViewSet)
resources_router.register(r'skills', main_views.PartnerSkillViewSet)
resources_router.register(r'tests', main_views.TestViewSet, base_name='test')


urlpatterns = [
    url(r'^', include([
        url(r'^invite_client/$', auth_views.InviteClientAPIView.as_view(), name='invite-client'),
        url(r'^contact_us/$', auth_views.ContactUsAPIView.as_view(), name='contact-us'),
        url(r'^suggest_us/$', auth_views.SuggestUsAPIView.as_view(), name='suggest-us'),
        url(r'^password_reset/$', auth_views.PasswordResetAPIView.as_view(), name='password-reset'), 
        url(r'^password_reset_confirm/$', auth_views.PasswordResetConfirmAPIView.as_view(), name='password-reset-confirm'),
        url(r'^change_email_confirm/$', auth_views.ChangeEmailConfirmAPIView.as_view(), name='change-email-confirm'),
        url(r'^token_auth/$', auth_views.obtain_jwt_token, name='token-auth'),

        url(r'^', include(users_router.urls)),
        url(r'^', include(detail_router.urls)),
        url(r'^resources/', include(resources_router.urls)),

        url(r'^resources/academic_options/$', main_views.AcademicOptionsUserView.as_view()),
        url(r'^resources/payment_constants/$', main_views.PaymentConstantsView.as_view()),

        # Admin app url
        url(r'^', include('admin.urls')),
    ]))
]
