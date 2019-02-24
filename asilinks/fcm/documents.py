
from django.utils.translation import ugettext_lazy as _
from mongoengine import fields, document, queryset

from .settings import FCM_DJANGO_SETTINGS as SETTINGS
from .fcm import fcm_send_bulk_message, fcm_send_message


def format_content(*args, **kwargs):
    context = kwargs.get('context', {})
    formated = []
    for item in args:
        if isinstance(item, str):
            try:
                formated.append(item.format(**context))
            except KeyError as e:
                raise KeyError('No se adjuntó la variable de contexto: {}'.format(e))
        else:
            formated.append(item)

    return tuple(formated)

class Device(document.Document):
    name = fields.StringField(max_length=255, verbose_name=_("Name"), blank=True, null=True)
    active = fields.BooleanField(
        verbose_name=_("Is active"), default=True,
        help_text=_("Inactive devices will not be sent notifications")
    )
    owner = fields.ReferenceField('Account', blank=True, null=True)
    date_created = fields.DateTimeField(
        verbose_name=_("Creation date"), null=True
    )

    meta = {'allow_inheritance': True}

    def __str__(self):
        return (
            self.name or str(self.device_id or "") or
            "%s for %s" % (self.__class__.__name__, self.owner or "unknown account")
        )


class FCMDeviceQuerySet(queryset.QuerySet):
    def send_message(self, title=None, body=None, icon=None, data=None, sound=None, badge=None, api_key=None, **kwargs):
        title, body = format_content(title, body, context=kwargs.pop('context', {}))

        if self:

            reg_ids = list(self(active=True).values_list('registration_id'))
            if len(reg_ids) == 0:
                return [{'failure': len(self), 'success': 0}]

            result = fcm_send_bulk_message(
                registration_ids=reg_ids,
                title=title,
                body=body,
                icon=icon,
                data=data,
                sound=sound,
                badge=badge,
                api_key=api_key,
                **kwargs
            )

            results = result['results']
            for (index, item) in enumerate(results):
                
                if 'error' in item:
                    reg_id = reg_ids[index]
                    self(registration_id=reg_id).update(active=False)

                    if SETTINGS["DELETE_INACTIVE_DEVICES"]:
                        self(registration_id=reg_id).delete()
            return result


class FCMDevice(Device):
    DEVICE_TYPES = (
        'ios',
        'android',
        'web'
    )

    device_id = fields.StringField(
        verbose_name=_("Device ID"), blank=True, null=True, db_index=True,
        help_text=_("Unique device identifier"),
        max_length=150
    )
    registration_id = fields.StringField(verbose_name=_("Registration token"))
    type = fields.StringField(choices=DEVICE_TYPES)
    # objects = FCMDeviceQuerySet()

    meta = {'queryset_class': FCMDeviceQuerySet}

    def send_message(self, title=None, body=None, icon=None, data=None, sound=None, badge=None, api_key=None, **kwargs):
        title, body = format_content(title, body, context=kwargs.pop('context', {}))

        result = fcm_send_message(
            registration_id=self.registration_id,
            title=title,
            body=body,
            icon=icon,
            data=data,
            sound=sound,
            badge=badge,
            api_key=api_key,
            **kwargs
        )

        device = FCMDevice.objects(registration_id=self.registration_id)
        if 'error' in result['results'][0]:
            device.update(active=False)

            if SETTINGS["DELETE_INACTIVE_DEVICES"]:
                device.delete()

        return result
