
import datetime as dt
import uuid
import bson
import six

from calendar import timegm
from datetime import datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from django.contrib.auth.tokens import PasswordResetTokenGenerator

from rest_framework_jwt.compat import get_username
from rest_framework_jwt.compat import get_username_field

def load_private_key(file_path):
    with open(file_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(), password=None, backend=default_backend())

    return private_key

def jwt_payload_handler(user):
    from rest_framework_jwt.settings import api_settings

    username_field = get_username_field()
    username = get_username(user)

    payload = {
        'user_id': user.pk,
        username_field: username,
        'lpc': str(user.last_password_change),
        'is': 'is' if user.is_staff else '',
        'exp': datetime.utcnow() + api_settings.JWT_EXPIRATION_DELTA
    }
    if isinstance(user.pk, uuid.UUID) or isinstance(user.pk, bson.ObjectId):
        payload['user_id'] = str(user.pk)

    # Include original issued at time for a brand new token,
    # to allow token refresh
    if api_settings.JWT_ALLOW_REFRESH:
        payload['orig_iat'] = timegm(
            datetime.utcnow().utctimetuple()
        )

    if api_settings.JWT_AUDIENCE is not None:
        payload['aud'] = api_settings.JWT_AUDIENCE

    if api_settings.JWT_ISSUER is not None:
        payload['iss'] = api_settings.JWT_ISSUER

    return payload

def jwt_response_payload_handler(token, user=None, request=None):
    # from authentication.serializers import SelfAccountSerializer
    return {
        'token': token,
        # **SelfAccountSerializer(user).data
    }

def jwt_get_username_from_payload_handler(payload):
    """
    Override this function if username is formatted differently in payload
    """
    return payload.get('email')

def save_last_login(user):
    """
    Saves user last login date
    """
    user.last_login = dt.datetime.utcnow()
    user.save(update_fields=['last_login'])


class EmailChangeTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, account, timestamp):
        return (
            six.text_type(account.id) + six.text_type(timestamp) +
            six.text_type(account.email)
        )

email_token_generator = EmailChangeTokenGenerator()
