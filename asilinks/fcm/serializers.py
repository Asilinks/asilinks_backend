
from rest_framework_mongoengine.serializers import DocumentSerializer
from rest_framework.serializers import ValidationError

from .documents import FCMDevice
from .settings import FCM_DJANGO_SETTINGS as SETTINGS


class FCMDeviceSerializer(DocumentSerializer):

    class Meta:
        model = FCMDevice
        fields = ("registration_id", "date_created", "type", 'name', )
        read_only_fields = ("date_created",)
        extra_kwargs = {
            'registration_id': {'required': True},
            'type': {'required': True},
        }

    def validate(self, data):
        devices = None
        owner = self.context['request'].user
        Device = self.Meta.model

        # if request authenticated, unique together with registration_id and user
        devices = Device.objects.filter(registration_id=data["registration_id"])
        devices.filter(owner__ne=owner).update(active=False)
        devices = devices.filter(owner=owner)

        if devices:
            raise ValidationError({'registration_id': 'This field must be unique.'})
        return data
