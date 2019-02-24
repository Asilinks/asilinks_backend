import os
import datetime as dt

from django.core.files.base import ContentFile
from mongoengine import fields, document

from asilinks.fields import LocalStorageFileField
from asilinks.storage_backends import PrivateMediaStorage


class FileStored(document.EmbeddedDocument):
    file = LocalStorageFileField(upload_to='store/%Y%m/',
        storage=PrivateMediaStorage()
    )


class DeliverableStore(document.Document):
    date = fields.DateTimeField(default=dt.datetime.now)
    container = fields.GenericReferenceField()
    attachments = fields.EmbeddedDocumentListField(FileStored)

    @classmethod
    def store_request(cls, request):
        from requesting.documents import Request, Message
        instance = cls(container=request)

        for message in request.com_channel:
            if (message.type in (Message.TYPE_DOC, Message.TYPE_IMAGE)
                    and message.last_delivery):
                filename = os.path.split(message.attachment.file.name)[-1]
                content = ContentFile(message.attachment.file.read())
                f = FileStored()

                f.file.save(filename, content, save=False)
                message.attachment.file.close()
                instance.attachments.append(f)

        if instance.attachments:
            return instance.save()


class OpenSuggest(document.Document):
    email = fields.EmailField()
    endpoint = fields.StringField()
    date = fields.DateTimeField(default=dt.datetime.now)
    content = fields.DictField()
