# Model imports
from .documents import Article

# Rest framework imports
from rest_framework import serializers, fields
from rest_framework.exceptions import ValidationError
from rest_framework_mongoengine.serializers import DocumentSerializer


class ArticleSerializer(DocumentSerializer):

    class Meta:
        model = Article
        fields = '__all__'
