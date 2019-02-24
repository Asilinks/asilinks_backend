from __future__ import absolute_import
import datetime as dt
import pandas as pd
import logging

from celery import shared_task

from main.documents import (Partner, KnowField,
    Category, PartnerStatisticalSummary)
from requesting.tasks import calc_partners_weights

from authentication.documents import Account


def calc_sponsors_weights(queryset):
    # Realiza query, convirtiendo el resumen estadistico en DataFrame.
    df = pd.DataFrame([
        {'id': ac.id, 'level': ac.sponsor_level, 
        **ac.sponsor_statistical_summary.to_mongo().to_dict()}
        for ac in queryset
    ])
    df.set_index('id', inplace=True)

    # Aplica normalizacion directa e inversa a los campos respectivos.
    direct_norm = lambda x: (x - x.min()) / (x.max() - x.min())
    inverse_norm = lambda x: (x.max() - x) / (x.max() - x.min())

    normalized = df.transform({
        'client_interval_average': inverse_norm,
        'partner_interval_average': inverse_norm,
        'client_rating_average': direct_norm,
        'partner_rating_average': direct_norm,
        'client_referred_count': direct_norm,
        'partner_referred_count': direct_norm,
        'monthly_referred_average': direct_norm,
    })

    # Multiplica por los pesos y los suma
    weights = {
        'client_interval_average': 0.1,
        'partner_interval_average': 0.1,
        'client_rating_average': 0.2,
        'partner_rating_average': 0.2,
        'client_referred_count': 0.1,
        'partner_referred_count': 0.1,
        'monthly_referred_average': 0.2,
    }

    df['feat'] = (normalized * weights).sum(axis=1)
    return df


@shared_task(name='partners_levelup')
def partners_levelup_selection():
    df = pd.DataFrame([
        {'partner': s, 'level': s.level, **s.statistical_summary.to_mongo().to_dict()}
        for s in Partner.objects.all()])
    df.set_index('partner', inplace=True)

    centroid = df.groupby('level').mean()
    euclidean_distance = pd.DataFrame()
    for level in (Partner.LEVEL_GOLD, Partner.LEVEL_SILVER, Partner.LEVEL_BRONZE):
        euclidean_distance[level] = (df.drop('level', axis=1) - centroid.loc[level]).pow(2).sum(axis=1).pow(0.5)

    df['close_distance'] = euclidean_distance.idxmin(axis=1)
    df.query('level != close_distance').apply(axis=1,
        func=lambda x: x.name.change_level(x.close_distance))


def partners_levelup_manual(level, n=5):
	next_level = {Partner.LEVEL_BRONZE: Partner.LEVEL_SILVER,
		Partner.LEVEL_SILVER: Partner.LEVEL_GOLD}

	queryset = Partner.objects.all()
	df = calc_partners_weights(queryset)
	df.sort_values('feat', ascending=False, inplace=True)
	df[df['level'] == level][:n]

	for p in queryset.filter(id__in=df[df['level'] == level][:n].index):
		p.change_level(next_level[level])


@shared_task(name='sponsors_levelup')
def sponsors_levelup_selection():
    df = pd.DataFrame([
        {'account': ac, 'level': ac.sponsor_level,
        **ac.sponsor_statistical_summary.to_mongo().to_dict()}
        for ac in Account.objects.all()])
    df.set_index('account', inplace=True)

    centroid = df.groupby('level').mean()
    euclidean_distance = pd.DataFrame()
    for level in (Account.LEVEL_A, Account.LEVEL_B, Account.LEVEL_C):
        euclidean_distance[level] = (
            df.drop('level', axis=1) - centroid.loc[level]).pow(2).sum(axis=1).pow(0.5)

    df['close_distance'] = euclidean_distance.idxmin(axis=1)
    df.query('level != close_distance').apply(axis=1,
        func=lambda x: x.name.modify(sponsor_level=x.close_distance))


def sponsors_levelup_manual(level, n=5):
	next_level = {Account.LEVEL_C: Account.LEVEL_B,
        Account.LEVEL_B: Account.LEVEL_A}

	queryset = Account.objects.all()
	df = calc_sponsors_weights(queryset)
	df.sort_values('feat', ascending=False, inplace=True)
	df[df['level'] == level][:n]

	for ac in queryset.filter(id__in=df[df['level'] == level][:n].index):
		ac.modify(sponsor_level=next_level[level])


@shared_task(name='eject_partner')
def eject_partner():
    """
    If partner does not satisfies
    minimum Asilinks quality
    it will be ejected
    """
    # Get dataframe
    df = pd.DataFrame([
        {
            'id': partner.id,
            'canceled_count': len(partner.requests_canceled),
            'done_count': len(partner.requests_done)
        }
        for partner in Partner.objects.filter(enabled=True)
    ])
    # Add required columns
    df['total'] = df['canceled_count'] + df['done_count']
    df['canceled_rate'] = df['canceled_count'] / df['total']
    # Fill NaN
    df.fillna(0, inplace=True)
    # Filter unsubscribable partners
    unsubscribe_df = df[
        ((df['total'] < 20) & (df['canceled_count'] > 2)) |
        ((df['total'] < 50) & (df['total'] >= 20) & (df['canceled_rate'] > 0.1)) |
        ((df['total'] < 1000) & (df['total'] >= 50) & (df['canceled_rate'] > 0.05)) |
        ((df['total'] >= 1000) & (df['canceled_rate'] > 0.01))
    ]
    Partner.objects(id__in=list(unsubscribe_df['id'])).modify(enabled=False)

@shared_task(name='check_partners_availability')
def check_partners_availability():

    KnowField.objects.all().update(enable=False)
    selected = {know for p in Partner.objects.all() for know in p.know_fields}
    [item.update(enable=True) for item in selected]

    Category.objects.all().update(enable=False)
    Category.objects.filter(name__in={kf.category for kf in selected}).update(enable=True)
