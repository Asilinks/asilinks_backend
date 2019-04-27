"""
BackOffice viewsets
"""
# Django imports
from django.utils.translation import ugettext_lazy as _
# Rest framework imports
from rest_framework import mixins, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
# Mongo rest framework imports
from rest_framework_mongoengine import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
# Model imports
from .documents import Article
# Serializer imports
from .serializers import (ArticleSerializer)


# Base class for views
class NoDeleteModelView(mixins.CreateModelMixin,
                        mixins.RetrieveModelMixin,
                        mixins.UpdateModelMixin,
                        mixins.ListModelMixin,
                        viewsets.GenericViewSet):
    """
	Base Model View for BackOffice endpoints
	"""
    # permission_classes = (IsAuthenticated, IsAdminUser,)
    pass


class ArticleViewSet(NoDeleteModelView):
    """
    GESTIÓN DE ARTÍCULOS
    """
    serializer_class = ArticleSerializer

    def get_queryset(self):
        return Article.objects.all()
