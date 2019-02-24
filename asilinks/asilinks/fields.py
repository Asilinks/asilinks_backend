import os
import datetime as dt

from django.db.models.fields.files import FieldFile
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.utils.encoding import force_str, force_text
from django.utils import six

from mongoengine.base import BaseField
from mongoengine.fields import DateTimeField
# from mongoengine.python_support import str_types

from rest_framework.relations import PrimaryKeyRelatedField


# Document Fields

class DateField(DateTimeField):

    def to_python(self, value):
        """Convert a MongoDB-compatible type to a Python type."""
        return value.date() if isinstance(value, dt.datetime) else value


class TimeDeltaField(BaseField):
    """32-bit integer field."""

    # def __init__(self, min_value=None, max_value=None, **kwargs):
    #     self.min_value, self.max_value = min_value, max_value
    #     super().__init__(**kwargs)

    def to_python(self, value):
        """Convert a MongoDB-compatible type to a Python type."""
        if isinstance(value, dt.timedelta):
            return value
        try:
            # value = int(value)
            value = dt.timedelta(hours=int(value))
        except ValueError:
            pass
        return value

    def to_mongo(self, value):
        """Convert a Python type to a MongoDB-compatible type."""
        return self.to_hours(value)

    def validate(self, value):
        if not isinstance(value, dt.timedelta):
            self.error('Debe ser timedelta')
        # try:
        #     value = int(value)
        # except Exception:
        #     self.error('%s could not be converted to int' % value)

        # if self.min_value is not None and value < self.min_value:
        #     self.error('Integer value is too small')

        # if self.max_value is not None and value > self.max_value:
        #     self.error('Integer value is too large')

    def prepare_query_value(self, op, value):
        if value is None:
            return value

        return super().prepare_query_value(op, self.to_hours(value))

    def to_hours(self, value):
        return value // dt.timedelta(hours=1)


class LocalStorageFileField(BaseField):

    proxy_class = FieldFile

    def __init__(self, size=None, name=None, upload_to='', storage=None, **kwargs):
        self.size = size
        self.storage = storage or default_storage
        self.upload_to = upload_to
        self.max_length = kwargs.get('max_length', None)
        if callable(upload_to):
            self.generate_filename = upload_to
        super().__init__(**kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        file = instance._data.get(self.name)

        # if file is None:
        # if isinstance(file, str_types) or file is None:
        if isinstance(file, str) or file is None:
            attr = self.proxy_class(instance, self, file)
            instance._data[self.name] = attr

        return instance._data[self.name]

    def __set__(self, instance, value):

        key = self.name
        if isinstance(value, File) and not isinstance(value, FieldFile):
            file = instance._data.get(self.name)
            if file:
                try:
                    file.delete()
                except:
                    pass
            # Create a new proxy object as we don't already have one
            file_copy = self.proxy_class(instance, self, value.name)
            file_copy.file = value
            instance._data[key] = file_copy
        else:
            instance._data[key] = value

        instance._mark_as_changed(key)

    def get_directory_name(self):
        return os.path.normpath(force_text(
            dt.datetime.now().strftime(force_str(self.upload_to))))

    def get_filename(self, filename):
        return os.path.normpath(
            self.storage.get_valid_name(os.path.basename(filename)))

    def generate_filename(self, instance, filename):
        return os.path.join(
            self.get_directory_name(), self.get_filename(filename))

    def to_mongo(self, value):
        if isinstance(value, self.proxy_class):
            return value.name
        return value


# Serializer Fields

class PrimaryKeyStringRelatedField(PrimaryKeyRelatedField):

    def to_representation(self, value):
        return six.text_type(value)
