from datetime import datetime

from rest_framework import permissions
from rest_framework_mongoengine import viewsets

from .documents import FCMDevice
from .serializers import FCMDeviceSerializer
from .permissions import IsOwner

# Create your views here.


class FCMDeviceViewSet(viewsets.ModelViewSet):
    queryset = FCMDevice.objects.all()
    serializer_class = FCMDeviceSerializer
    lookup_field = "registration_id"

    permission_classes = (permissions.IsAuthenticated, IsOwner)

    def get_queryset(self):
        # filter all devices to only those belonging to the current user
        return FCMDevice.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, date_created=datetime.now())
