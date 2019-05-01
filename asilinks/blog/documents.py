from django.core.files.base import ContentFile
from mongoengine import fields, document
from asilinks.fields import LocalStorageFileField
from asilinks.storage_backends import PublicOverrideMediaStorage

class Article(document.Document):
    active = fields.BooleanField(default=True)
    body = fields.StringField(max_length=10000)
    title = fields.StringField(max_length=500)
    author = fields.StringField(max_length=255)
    draft = fields.BooleanField(default=False)
    author_image = LocalStorageFileField(upload_to='blog/',
        default='blog/default.png', storage=PublicOverrideMediaStorage())