import datetime as dt
from django.core.files.base import ContentFile
from mongoengine import fields, document
from asilinks.fields import LocalStorageFileField
from main.documents import Category
from asilinks.storage_backends import PublicOverrideMediaStorage

class Article(document.Document):
    active = fields.BooleanField(default=True)
    body = fields.StringField(max_length=10000)
    title = fields.StringField(max_length=500)
    author = fields.StringField(max_length=255)
    draft = fields.BooleanField(default=False)
    category = fields.ReferenceField(Category)
    article_image = LocalStorageFileField(upload_to='blog/',
        default='blog/article_default.png', storage=PublicOverrideMediaStorage())
    author_image = LocalStorageFileField(upload_to='blog/',
        default='blog/author_default.png', storage=PublicOverrideMediaStorage())
    created_at = fields.DateTimeField(default=dt.datetime.now)