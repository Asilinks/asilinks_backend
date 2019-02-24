from bson import ObjectId
import weasyprint

from django.conf import settings

from rest_framework import renderers
from rest_framework.utils import encoders


class JSONMongoEncoder(encoders.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


class JSONMongoRenderer(renderers.JSONRenderer):
    encoder_class = JSONMongoEncoder


class PdfRenderer(renderers.TemplateHTMLRenderer):
    """
        Renders a PDF based on a html template with easyprint.
    """

    format = 'pdf'
    media_type = 'application/pdf'

    def render(self, data, accepted_media_type=None, renderer_context=None):       
        html = super().render(data, accepted_media_type, renderer_context)
        return weasyprint.HTML(string=html).write_pdf()
