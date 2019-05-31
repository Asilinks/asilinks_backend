# Rest framework imports
from rest_framework.routers import DefaultRouter

# Django imports
from django.conf.urls import url, include

# Own imports
from .views import (ArticleViewSet, ArticleListViewSet)

router = DefaultRouter()
router.register(r'articles', ArticleViewSet, base_name='blog-article')
router.register(r'article-list', ArticleListViewSet, base_name='blog-article-list')

urlpatterns = [
	url(r'^blog/', include(router.urls)),
]
