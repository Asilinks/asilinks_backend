# Model imports
from .documents import Article

# Rest framework imports
from rest_framework import serializers, fields
from rest_framework.exceptions import ValidationError
from rest_framework_mongoengine.serializers import DocumentSerializer

# Custom imports
from asilinks.validators import file_max_size


class ArticleSerializer(DocumentSerializer):

    author_image = fields.ImageField(use_url=True, required=False, 
        default='blog/default.png', validators=[file_max_size])

    class Meta:
        model = Article
        fields = '__all__'

    def create(self, validated_data):

        instance = Article(**validated_data)
        instance.save()

        # if 'article_image' in validated_data:
        #     name = 'asi-{}.{}'.format(instance.id, validated_data['article_image'].name.split('.')[-1])
        #     instance.article_image.save(name, validated_data.get('article_image'))

        if 'author_image' in validated_data:
            name = 'asi-{}.{}'.format(instance.id, validated_data['author_image'].name.split('.')[-1])
            instance.author_image.save(name, validated_data.get('author_image'))
        
        return instance


    def update(self, instance, validated_data):
        
        # instance.save()

        # if 'article_image' in validated_data:
        #     name = 'asi-{}.{}'.format(instance.id, validated_data['article_image'].name.split('.')[-1])
        #     instance.article_image.save(name, validated_data.get('article_image'))
        
        if 'author_image' in validated_data:
            name = 'asi-{}.{}'.format(instance.id, validated_data['author_image'].name.split('.')[-1])
            instance.author_image.save(name, validated_data.get('author_image'))
        
        return instance
