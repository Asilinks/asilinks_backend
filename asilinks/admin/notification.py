"""
Contains all notification messages
"""

CLIENT_MESSAGES = {
    'question_answered': {
        'title': 'Tienes un nuevo mensaje.',
        'body': 'En el requerimiento "{request.name}"',
    },
    'round_partner_made_offer': {
        'title': 'Tienes una propuesta.',
        'body': 'En el requerimiento "{request.name}"',
    },
    'have_new_message': {
        'title': 'Tienes un nuevo mensaje.',
        'body': 'En el requerimiento "{request.name}"',
    },
    'request_delivered': {
        'title': 'Su requerimiento "{request.name}" esta listo.',
        'body': None,
    },
    'extension_requested': {
        'title': 'El socio en el requerimiento "{request.name}" solicitó una extensión de tiempo',
        'body': None,
    },
    'requests_canceled': {
        'title': 'El requerimiento "{request.name}" ha sido dado de baja.',
        'body': 'El plazo establecido por el socio a caducado.',
    },
    'were_qualified': {
        'title': 'Fuiste calificado en el requerimiento "{request.name}"',
        'body': 'Revisa tu nota',
    },
    'partner_not_chosen': {
        'title': 'En la oportunidad "{request.name}" no fuiste seleccionado.',
        'body': None,
    },
    'partner_not_found': {
        'title': 'Buscando socio...',
        'body': 'En el requerimiento "{request.name}" no tenemos socios registrados.',
    },
}

PARTNER_MESSAGES = {
    'have_an_opportunity': {
        'title': 'Tienes una oportunidad.',
        'body': None,
    },
    'have_pending_requirement': {
        'title': 'Tienes una oportunidad pendiente.',
        'body': None,
    },
    'updated_description_requirement': {
        'title': 'El cliente ha actualizado la descrpción.',
        'body': 'En la oportunidad "{request.name}"',
    },
    'have_new_message': {
        'title': 'Tienes un nuevo mensaje.',
        'body': 'En la oportunidad "{request.name}"',
    },
    'were_rejected': {
        'title': 'El cliente aceptó otra propuesta.',
        'body': 'En la oportunidad "{request.name}"',
    },
    'were_selected': {
        'title': 'El cliente aceptó tu propuesta.',
        'body': 'En la oportunidad "{request.name}"',
    },
    'client_satisfied': {
        'title': 'El cliente está satisfecho con tu producto.',
        'body': 'Tu pago será liberado.',
    },
    'request_unsatisfied': {
        'title': 'El cliente está insatisfecho.',
        'body': 'En la oportunidad "{request.name}"',
    },
    'level_up': {
        'title': 'Enhorabuena subiste a la categoría "{partner.level}"',
        'body': None,
    },
    'client_cancel_request': {
        'title': 'El cliente dió de baja la oportunidad "{request.name}"',
        'body': None,
    },
    'request_was_canceled': {
        'title': 'La oportunidad "{request.name}" fue dada de baja.',
        'body': 'El cliente no eligió un socio en el tiempo establecido.',
    },
    'requests_canceled': {
        'title': 'La oportunidad "{request.name}" ha sido dada de baja.',
        'body': 'El tiempo de la extensión ha finalizado.',
    },
    'were_qualified': {
        'title': 'Fuiste calificado en la oportunidad "{request.name}".',
        'body': 'Revisa tu nota.',
    },
    'level_down': {
        'title': 'Has bajado a la categoría "{partner.level}"',
        'body': None,
    },
    'test_available': {
        'title': 'Puedes subir de categoría.',
        'body': 'Presenta la prueba.',
    },
    'level_back': {
        'title': 'Felicidades subiste a la categoría "{partner.level}"',
        'body': None,
    },
    'extension_approved': {
        'title': 'Solicitud de extensión de tiempo aprobada.',
        'body': 'La extensión de tiempo que solicitaste fue aprobada.',
    },
    'extension_rejected': {
        'title': 'Solicitud de extensión de tiempo rechazada.',
        'body': 'La extensión de tiempo que solicitaste fue rechazada.',
    },
}
