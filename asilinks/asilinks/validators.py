from functools import reduce
import logging
import magic

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.core.files.uploadedfile import UploadedFile

from rest_framework.exceptions import ValidationError


class RequireObservableTrue(logging.Filter):
    def filter(self, record):
        return settings.OBSERVABLE_LOGS


class FileMimetypeValidator():
    message = _('The mimetype field {mimetype} is not valid for {type} type.')

    def __init__(self, options, field, mimetype_field=None):
        self.field = field
        self.mimetype_field = mimetype_field
        self.options = options

    def __call__(self, attrs):
        if not self.field in attrs:
            return

        file = attrs[self.field].file
        mimetype = magic.from_buffer(file.read(), mime=True)

        if self.mimetype_field:
            type_attr = attrs[self.mimetype_field]
            options = self.options.get(type_attr, [])
        else:
            type_attr = 'doc, image or voice'
            options = reduce(lambda x, y: x+y, self.options.values())

        if not mimetype in options:
            message = self.message.format(mimetype=mimetype, type=type_attr)
            raise ValidationError({self.field: message})

def file_max_size(value: UploadedFile):
    if value.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        max_size_kb = settings.FILE_UPLOAD_MAX_MEMORY_SIZE // 1024
        msg = _('El archivo adjunto no puede tener un tamaño mayor a {} KB.')
        raise ValidationError(msg.format(max_size_kb))
