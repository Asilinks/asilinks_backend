from django.core.files.base import ContentFile
from mongoengine import fields, document

class Article(document.Document):
    active = fields.BooleanField(default=True)
    body = fields.StringField(max_length=10000)
    title = fields.StringField(max_length=500)
    author = fields.StringField(max_length=255)
    draft = fields.BooleanField(default=False)