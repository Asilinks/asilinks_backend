# Model imports
from .documents import Article

# Rest framework imports
from rest_framework import serializers, fields
from rest_framework.exceptions import ValidationError
from rest_framework_mongoengine.serializers import DocumentSerializer

# Custom imports
from asilinks.validators import file_max_size


class ArticleSerializer(DocumentSerializer):
    category_name = serializers.SerializerMethodField()

    article_image = fields.ImageField(use_url=True, required=False, 
        default='blog/article_default.png', validators=[file_max_size])
    author_image = fields.ImageField(use_url=True, required=False, 
        default='blog/author_default.png', validators=[file_max_size])

    class Meta:
        model = Article
        fields = '__all__'

    def get_category_name(self, instance):
        return instance.category.name if instance.category else None

    def create(self, validated_data):

        instance = Article(**validated_data)
        if instance.draft:
            instance.active = False
        instance.save()

        if 'article_image' in validated_data:
            name = 'asi-article-{}.{}'.format(instance.id, validated_data['article_image'].name.split('.')[-1])
            instance.article_image.save(name, validated_data.get('article_image'))

        if 'author_image' in validated_data:
            name = 'asi-author-{}.{}'.format(instance.id, validated_data['author_image'].name.split('.')[-1])
            instance.author_image.save(name, validated_data.get('author_image'))
        
        return instance

    def update(self, instance, validated_data):
        instance.active = validated_data.get('active', instance.active)
        instance.body = validated_data.get('body', instance.body)
        instance.title = validated_data.get('title', instance.title)
        instance.author = validated_data.get('author', instance.author)
        instance.draft = validated_data.get('draft', instance.draft)
        instance.category = validated_data.get('category', instance.category)
        instance.created_at = validated_data.get('created_at', instance.created_at)
        instance.save()

        if 'article_image' in validated_data:
            name = 'asi-{}.{}'.format(instance.id, validated_data['article_image'].name.split('.')[-1])
            instance.article_image.save(name, validated_data.get('article_image'))
        
        if 'author_image' in validated_data:
            name = 'asi-{}.{}'.format(instance.id, validated_data['author_image'].name.split('.')[-1])
            instance.author_image.save(name, validated_data.get('author_image'))

        return instance
