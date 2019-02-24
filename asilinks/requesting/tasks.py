from __future__ import absolute_import
import datetime as dt
import pandas as pd

from mongoengine.queryset.visitor import Q
from celery import shared_task
from celery.utils.log import get_task_logger

from .documents import Request, RoundPartner
from authentication.documents import Location
from main.documents import Partner
from payments.documents import Bill
from admin.notification import CLIENT_MESSAGES, PARTNER_MESSAGES

logger = get_task_logger(__name__)

def calc_partners_weights(queryset):
    # Realiza query, convirtiendo el resumen estadistico en DataFrame.
    df = pd.DataFrame([
        {'id': s.id, 'level': s.level, **s.statistical_summary.to_mongo().to_dict()}
        for s in queryset
    ])
    df.set_index('id', inplace=True)

    # Aplica normalizacion directa e inversa a los campos respectivos.
    direct_norm = lambda x: (x - x.min()) / (x.max() - x.min())
    inverse_norm = lambda x: (x.max() - x) / (x.max() - x.min())

    normalized = df.transform({
        'done_count': direct_norm,
        'done_time_average': inverse_norm,
        'canceled_count': inverse_norm,
        'offered_percent': direct_norm,
        'done_score_average': direct_norm,
        'academics_count': direct_norm,
        'experience_years': direct_norm,
        'accept_time_average': direct_norm,
        'price_average': direct_norm,
    })

    # Multiplica por los pesos y los suma
    weights = {
        'done_count': 0.1,
        'done_time_average': 0.15,
        'canceled_count': 0.15,
        'offered_percent': 0.1,
        'done_score_average': 0.2,
        'academics_count': 0.05,
        'experience_years': 0.05,
        'accept_time_average': 0.1,
        'price_average': 0.1,
    }

    df['feat'] = (normalized * weights).sum(axis=1)
    return df

def select_partners(queryset, samples=4):
    df = calc_partners_weights(queryset)

    # Selecciona la muestra aleatoria con pesos
    # selected = df.sample(n=samples, weights='feat')
    selected = []
    for l in (Partner.LEVEL_BRONZE, Partner.LEVEL_SILVER, Partner.LEVEL_GOLD):
        part = df[df.level == l]
        n = min(part.shape[0], samples)

        # En condiciones iniciales cero, inicializa los pesos en 1.
        if part['feat'].sum() == 0:
            part['feat'] = 1

        # Si existe una muestra seleccionable para esa categoria los agrega.
        if n > 0:
            selected.append(part.sample(n=n, weights='feat'))

    return queryset.filter(id__in=pd.concat(selected).index)

@shared_task(name='select_round_partners')
def select_round_partners(instance_id, *args, **kwargs):
    now = dt.datetime.now()
    instance = Request.objects.get(id=instance_id)

    # Filtra socios favoritos por area de conocimiento.
    favorite_partners = list({fp.partner
        for fp in instance.client.favorite_partners
        if fp.know_field in instance.know_fields})

    filters = {
        'enabled': True,
        'know_fields__in': instance.know_fields,
        'id__nin': [fp.id for fp in favorite_partners],
    }

    if instance.country_alpha2:
        filters['residence__in'] = Location.objects.filter(
            alpha2_code=instance.country_alpha2)

    if instance.client.account.has_partner_profile():
        filters['id__nin'].append(instance.client.account.partner_profile.id)

    round_partners = list()
    queryset = Partner.objects.filter(**filters)

    if not queryset:
        instance.client.account.send_message(context={'request': instance},
            data={'request_id': str(instance.id), 'profile': 'client'},
            **CLIENT_MESSAGES['partner_not_found'])
        return

    for partner in [*favorite_partners, *select_partners(queryset)]:

        round_partners.append(RoundPartner(
            partner=partner, date_notification=now))
        partner.modify(push__requests_todo=instance)
        ## TODO: partners de diferentes niveles
        partner.account.send_message(
            data={'request_id': str(instance.id), 'profile': 'partner'},
            **PARTNER_MESSAGES['have_an_opportunity'])

    instance.modify(round_partners=round_partners)
    # return round_partners


@shared_task(name='refresh_round_partners')
def refresh_round_partners():
    """
    Refresh round partners
    """
    # Constants
    notification_lower_limit = 1
    notification_upper_limit = 2
    cancelable_lower_limit = 6
    # Get only id and date created info from todo requests
    all_todo_requests = Request.objects.filter(status=Request.STATUS_TODO,
        date_created__lt=dt.datetime.now() - dt.timedelta(hours=36)).values_list('id', 'date_created')
    # Convert list of tuples -> list of lists -> dataframe
    all_todo_requests_dataframe = pd.DataFrame([list(elem) for elem in all_todo_requests], columns=['id', 'date'])
    # Create timedelta serie
    all_todo_requests_dataframe['cycles'] = all_todo_requests_dataframe['date'].apply(lambda x: (dt.datetime.now() - x).total_seconds() / dt.timedelta(hours=36).total_seconds())
    # Get notificable, refreshable and cancelable request lists
    notificable_requests = all_todo_requests_dataframe[
        (notification_lower_limit < all_todo_requests_dataframe['cycles']) & (all_todo_requests_dataframe['cycles'] < notification_upper_limit)
    ]
    refreshable_requests = all_todo_requests_dataframe[
        (notification_upper_limit < all_todo_requests_dataframe['cycles']) & (all_todo_requests_dataframe['cycles'] < cancelable_lower_limit)
    ]
    cancelable_requests = all_todo_requests_dataframe[
        all_todo_requests_dataframe['cycles'] > cancelable_lower_limit
    ]
    # Start process
    notify_todo_requests([str(id) for id in notificable_requests['id']])
    refresh_todo_requests([str(id) for id in refreshable_requests['id']])
    cancel_todo_requests([str(id) for id in cancelable_requests['id']])


@shared_task(name='notify_todo_requests')
def notify_todo_requests(ids):
    """
    Takes a dataframe and applies
    some action on each request id
    depending on the case value
    """

    logger.info('notificando a socios... {}'.format(ids))
    # Start loop
    for request_id in ids:
        # Get request
        request = Request.objects.get(id=request_id)
        # Get round partners
        round_partners = request.round_partners
        # loop over round partners
        for round_partner in round_partners:
            round_partner.partner.account.send_message(
                data={'request_id': str(request.id), 'profile': 'client'},
                **PARTNER_MESSAGES['have_pending_requirement'])


@shared_task(name='refresh_todo_requests')
def refresh_todo_requests(ids):
    """
    Get Refreshed round partners
    """
    logger.info('refrescando socios... {}'.format(ids))
    now = dt.datetime.now()
    # Start loop
    for instance_id in ids:
        # Get request
        instance = Request.objects.get(id=instance_id)

        # Prepare filters
        filters = {
            'enabled': True,
            'know_fields__in': instance.know_fields
        }

        if instance.country_alpha2:
            filters['residence__in'] = Location.objects.filter(
                alpha2_code=instance.country_alpha2)

        not_allowed_round_partners = list()
        if instance.client.account.has_partner_profile():
            not_allowed_round_partners.append(instance.client.account.partner_profile.id)

        # Get all round partners
        round_partners = instance.round_partners

        # Get round partners to refresh
        refreshable_round_partners = [
            round_partner for round_partner in round_partners if not round_partner.date_response
        ]

        # Reject round partners
        for rp in refreshable_round_partners:
            rp.rejected=True
            rp.save()

        # Append all round partners to filters
        for round_partner in round_partners:
            not_allowed_round_partners.append(round_partner.partner.id)
        filters['id__nin'] = not_allowed_round_partners

        queryset = Partner.objects.filter(**filters)

        if not queryset:
            instance.client.account.send_message(context={'request': instance},
                data={'request_id': str(instance.id), 'profile': 'client'},
                **CLIENT_MESSAGES['partner_not_found'])

        for partner in select_partners(queryset):

            round_partners.append(RoundPartner(
                partner=partner, date_notification=now))
            partner.modify(push__requests_todo=instance)
            ## TODO: partners de diferentes niveles
            partner.account.send_message(
                data={'request_id': str(instance.id), 'profile': 'client'},
                **PARTNER_MESSAGES['have_an_opportunity'])

        instance.modify(round_partners=round_partners)


@shared_task(name='cancel_todo_requests')
def cancel_todo_requests(ids):
    """
    Cancel inactive requests
    """
    logger.info('cancelando requerimientos... {}'.format(ids))
    for instance_id in ids:
        # Get request
        request = Request.objects.get(id=instance_id)

        request.client.modify(pull__requests_todo=request,
            push__requests_canceled=request)
        for rp in request.round_partners:
            if not rp.rejected:
                rp.partner.modify(pull__requests_todo=request,
                    push__requests_canceled=request)
                rp.partner.account.send_message(context={'request': request},
                    data={'request_id': str(request.id), 'profile': 'partner'},
                    **PARTNER_MESSAGES['request_was_canceled'])

        request.client.account.send_message(context={'request': request},
            data={'request_id': str(request.id), 'profile': 'client'},
            **CLIENT_MESSAGES['partner_not_chosen'])
        request.modify(status=Request.STATUS_CANCELED, date_canceled=dt.datetime.now())


@shared_task(name='unsatisfied_requests')
def cancel_unsatisfied_requests():
    requests = Request.objects.filter(status=Request.STATUS_UNSATISFIED,
        date_unsatisfied__lt=dt.datetime.now()-dt.timedelta(hours=48))

    for instance in requests:
        instance.refund()

        instance.partner.modify(pull__requests_in_progress=instance,
            push__requests_canceled=instance)
        instance.client.modify(pull__requests_in_progress=instance,
            push__requests_canceled=instance)
        instance.modify(status=Request.STATUS_CANCELED, date_canceled=dt.datetime.now())

        Bill.make_bill(instance)

        instance.partner.account.send_message(context={'request': instance},
            data={'request_id': str(instance.id), 'profile': 'partner'},
            **PARTNER_MESSAGES['client_cancel_request'])


@shared_task(name='failure_deadline_requests')
def failure_deadline_requests():
    requests = Request.objects.filter(status=Request.STATUS_IN_PROGRESS,
        date_promise__lt=dt.datetime.now() - dt.timedelta(days=7, hours=48))

    for instance in requests:
        instance.refund()

        instance.partner.modify(pull__requests_in_progress=instance,
            push__requests_canceled=instance)
        instance.client.modify(pull__requests_in_progress=instance,
            push__requests_canceled=instance)
        instance.modify(status=Request.STATUS_CANCELED, date_canceled=dt.datetime.now())

        Bill.make_bill(instance)

        instance.partner.account.send_message(context={'request': instance},
            data={'request_id': str(instance.id), 'profile': 'partner'},
            **PARTNER_MESSAGES['requests_canceled'])
        instance.client.account.send_message(context={'request': instance},
            data={'request_id': str(instance.id), 'profile': 'client'},
            **CLIENT_MESSAGES['requests_canceled'])


# @shared_task(name='inactive_round_partners')
# def check_inactive_round_partners():
#     todo_requests = Request.objects.filter(status=Request.STATUS_TODO)
#     # Loop over each request
#     for todo_request in todo_requests:
#         inactive_round_partners = [
#             # Select partner if it does not have last activity or it has more than 36 hours (one cycle)
#             round_partner for round_partner in todo_request.round_partners if not round_partner.last_activity or round_partner.last_activity < dt.datetime.now() - dt.timedelta(hours=12)
#         ]
#         # Send notification to each partner with pending request
#         for round_partner in inactive_round_partners:
#             round_partner.partner.account.send_message(
#               data={'request_id': str(instance.id), 'profile':'partner'},
#               **PARTNER_MESSAGES['have_pending_requirement'])


@shared_task(name='close_pending_requests')
def close_pending_requests():
    """
    Close pending requests
    """
    requests = Request.objects.filter(status=Request.STATUS_PENDING, 
        date_delivered__lt=dt.datetime.now() - dt.timedelta(hours=48))

    for instance in requests:
        instance.close()


@shared_task(name='clean_requests')
def clean_closed_requests():
    """
    Clean closed Requests
    """
    # Import Q function
    from mongoengine.queryset.visitor import Q
    # Search for done requests that have some amount of time closed
    Request.objects \
        .filter(
            Q(status=Request.STATUS_DONE,
              date_closed__lt=dt.datetime.now() - dt.timedelta(days=30)) & \
            (Q(questions__not__size=0) | Q(com_channel__not__size=0))) \
        .modify(com_channel=[],questions=[])

@shared_task(name='requests_without_partners')
def requests_without_partners():
    for req in Request.objects.filter(round_partners=[]):
        select_round_partners(str(req.id))
