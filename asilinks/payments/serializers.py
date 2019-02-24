
from rest_framework import serializers, fields
from rest_framework.reverse import reverse

from rest_framework_mongoengine.serializers import (
    DocumentSerializer, EmbeddedDocumentSerializer)

from .documents import Transaction
from requesting.documents import Request

class TransactionSerializer(DocumentSerializer):
    operation_display = serializers.ReadOnlyField(source='get_operation_display')
    name = serializers.ReadOnlyField(source='item.name')
    reference = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = ('amount', 'date', 'type', 'reference', 'operation',
            'operation_display', 'name', )

    def get_reference(self, instance):
        request = self.context['request']

        if isinstance(instance.item, Request) and instance.operation != Transaction.OP_SPONSOR_FEE:
            # return reverse('request-detail',
            #     kwargs={'id': instance.item.id}, request=request)
            return 'cliente/detalle-requerimiento?type=req&id={request_id}'.format(
                request_id=instance.item.id)

        return None
