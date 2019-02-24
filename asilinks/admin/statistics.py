"""
Statistics module
"""
# Python imports
import datetime as dt
import pandas as pd
from mongoengine.queryset.visitor import Q
# Document Models imports
from authentication.documents import Account
from requesting.documents import Request
from main.documents import Partner, Client, Category
from payments.documents import Transaction


def get_requests_dataframe(requests):
    """
    Returns a dataframe with all required request data
    """
    return pd.DataFrame(
        [
            [
                request.price,
                request.status,
                request.date_created,
                request.date_started,
                request.date_delivered,
                request.date_closed,
                request.date_canceled,
                request.date_promise,
                request.date_unsatisfied
            ]
            for request in requests
        ],
        columns=[
            'Price',
            'Status',
            'Date_Created',
            'Date_Started',
            'Date_Delivered',
            'Date_Closed',
            'Date_Canceled',
            'Date_Promise',
            'Date_Unsatisfied'
        ]
    )


def get_accounts_dataframe(accounts):
    """
    Returns a dataframe with all required accounts data
    """
    return pd.DataFrame(
        [
            [
                account.residence.country,
                account.residence.state,
                dt.date.today().year - account.birth_date.year,
                account.legal_docs,
                account.sponsor_level,
                account.date_joined,
                account.gender
            ]
            for account in accounts
        ],
        columns=[
            'Country',
            'State',
            'Age',
            'Legal_Docs',
            'Sponsor_Level',
            'Date_Joined',
            'Gender'
        ]
    )


def get_clients_dataframe(clients):
    """
    Returns a dataframe with all required clients data
    """
    return pd.DataFrame(
        [
            [
                client.rating,
                client.last_activity,
                client.commercial_sector,
                len(client.requests_todo),
                len(client.requests_in_progress),
                len(client.requests_done),
                len(client.requests_canceled),
                len(client.requests_draft),
            ]
            for client in clients
        ],
        columns=[
            'Rating',
            'Last_Activity',
            'Commercial_Sector',
            'Requests_To_Do',
            'Requests_in_Progress',
            'Requests_Done',
            'Requests_Canceled',
            'Requests Draft',
        ]
    )


def get_partners_dataframe(partners):
    """
    Returns a dataframe with all required partners data
    """
    return pd.DataFrame(
        [
            [
                partner.rating,
                partner.level,
                partner.know_fields,
                partner.joined_date,
                partner.enabled,
                len(partner.requests_todo),
                len(partner.requests_in_progress),
                len(partner.requests_rejected),
                len(partner.requests_done),
                len(partner.requests_canceled),
            ]
            for partner in partners
        ],
        columns=[
            'Rating',
            'Level',
            'Know fields',
            'Joined Date',
            'Enabled',
            'Requests_To_Do',
            'Requests_in_progress',
            'Requests_rejected',
            'Requests_done',
            'Requests_canceled',
        ]
    )


def get_transactions_dataframe():
    """
    Returns a dataframe with all required transactions data
    """
    pass


def first_day_at_mid():
    """
    Returns the first day of the month datetime
    """
    return dt.datetime.combine(
        dt.date.today().replace(day=1),
        dt.datetime.min.time()
    )

def get_level_number(data, member):
    try:
        level = data[member]
    except:
        level = 0
    return level


def get_user_statistics():
    # Get query sets
    ALL_ACCOUNTS = get_accounts_dataframe(Account.objects.all()) # pylint: disable=no-member
    return {
        'users_by_residence': get_users_by_residence(ALL_ACCOUNTS),
        'users_by_legal_docs': get_users_by_legal_docs(ALL_ACCOUNTS),
        'users_by_gender': get_users_by_gender(ALL_ACCOUNTS),
        'users_by_age': get_users_by_age(ALL_ACCOUNTS),
    }


#################################
####### Single statistics #######
#################################

def get_singular_statistics():
    """
    Summary of singular statistics
    """
    # Get first day if month at midnight
    FIRST_DAY = first_day_at_mid()
    # Get query sets
    ALL_ACCOUNTS = get_accounts_dataframe(Account.objects.all()) # pylint: disable=no-member
    ALL_CLIENTS = get_clients_dataframe(Client.objects.all()) # pylint: disable=no-member
    ALL_PARTNERS = get_partners_dataframe(Partner.objects.all()) # pylint: disable=no-member
    ALL_REQUESTS = get_requests_dataframe(Request.objects.all()) # pylint: disable=no-member

    return {
        'month_registered_users': get_month_registered_users(ALL_ACCOUNTS, FIRST_DAY),
        'number_total_users': get_number_total_users(ALL_ACCOUNTS),
        'number_active_clients': get_number_active_clients(ALL_CLIENTS),
        'number_active_partners': get_number_active_partners(ALL_PARTNERS),
        'total_profit': round(get_total_profit(), 2),
        'month_total_profit': round(get_month_total_profit(FIRST_DAY), 2),
        'total_partner_profit': round(get_total_partner_profit(), 2),
        'total_sponsor_profit': round(get_total_sponsor_profit(), 2),
        'total_withheld_payments': round(get_total_withheld_payments(), 2),
        'requirement_mean_cost': round(get_requirement_mean_cost(ALL_REQUESTS), 2),
        'canceled_requirement_profit': round(get_canceled_requirement_profit(), 2),
    }


def get_month_registered_users(accounts, first_day):
    """
    Returns the number of total new registered users this month
    """
    return len(accounts[accounts['Date_Joined'] > first_day])


def get_number_total_users(accounts):
    """
    Returns the number of user registered in the platform
    """
    return len(accounts)


def get_number_active_clients(clients):
    """
    Returns the number of active clients
    """
    return len(clients[clients['Last_Activity'] > dt.datetime.combine(dt.date.today(), dt.datetime.min.time()) - dt.timedelta(days=30)])


def get_number_active_partners(partners):
    """
    Returns the number of active partners
    """
    return len(partners[partners['Enabled']])


def get_total_profit():
    """
    Returns Asilinks total profit
    """
    return Transaction.objects \
        .filter(Q(operation=Transaction.OP_ASILINKS_FEE) |
                Q(operation=Transaction.OP_SPONSOR_FEE,
                  receiver=Account.default_sponsor_account())) \
        .sum('amount')


def get_month_total_profit(first_day):
    """
    Returns Asilinks month total profit
    """
    return Transaction.objects \
        .filter(Q(date__gte=first_day) &
                (Q(operation=Transaction.OP_ASILINKS_FEE) |
                 Q(operation=Transaction.OP_SPONSOR_FEE,
                   receiver=Account.default_sponsor_account()))) \
        .sum('amount')


def get_total_partner_profit():
    """
    Returns total partner profit
    """
    return Transaction.objects \
        .filter(operation=Transaction.OP_PARTNER_SETTLEMENT) \
        .sum('amount')


def get_total_sponsor_profit():
    """
    Returns total sponsor profit
    """
    return Transaction.objects \
        .filter(operation=Transaction.OP_SPONSOR_FEE,
                receiver__ne=Account.default_sponsor_account()).sum('amount')


def get_total_withheld_payments():
    """
    Returns total withheld payments
    (unclosed requirements)
    """
    return Transaction.objects \
        .filter(operation=Transaction.OP_REQUEST_PAYMENT).sum('amount')


def get_requirement_mean_cost(requests):
    """
    Returns requirement mean cost
    """
    return requests[requests['Status'] > 1].mean()['Price']


def get_canceled_requirement_profit():
    """
    Returns profit for canceled requirements
    """
    canceled_requests = Request.objects.filter(status=Request.STATUS_CANCELED) # pylint: disable=no-member
    total_profit_canceled_requests = 0
    for canceled_request in canceled_requests:
        for transaction in canceled_request.transactions:
            if transaction.operation == Transaction.OP_ASILINKS_FEE:
                total_profit_canceled_requests += transaction.amount
    return total_profit_canceled_requests


#################################
########## Pie Charts ###########
#################################


def get_partners_by_level():
    """
    Returns a dict with the number of
    partners by segment
    """
    partners = get_partners_dataframe(Partner.objects.all()) # pylint: disable=no-member
    partners_by_segment = partners.groupby('Level')['Level'].count()
    
    return [
        {
            'name': 'Black',
            'y': get_level_number(partners_by_segment, 'black'),
        },
        {
            'name': 'Platinum',
            'y': get_level_number(partners_by_segment, 'platinum'),
        },
        {
            'name': 'Gold',
            'y': get_level_number(partners_by_segment, 'gold'),
        },
        {
            'name': 'Silver',
            'y': get_level_number(partners_by_segment, 'silver'),
        },
        {
            'name': 'Bronze',
            'y': get_level_number(partners_by_segment, 'bronze'),
        },
    ]


def get_requests_by_status():
    """
    Returns a dict with the number of
    requests by status
    """
    requests = get_requests_dataframe(Request.objects.all())
    requests_grouped_by_status = requests.groupby('Status')['Status'].count()
    requests_by_status = list()
    STATUS_TYPES = [ # pylint: disable=invalid-name
        'To Do',
        'In Progress',
        'Delivered',
        'Pending',
        'Done',
        'Canceled',
        'Unsatisfied'
    ]
    for status, i in zip(STATUS_TYPES, range(1, 8)):
        try:
            requests_by_status.append({'name': status, 'y': requests_grouped_by_status[i]})
        except KeyError:
            requests_by_status.append({'name': status, 'y': 0})
    return requests_by_status


#################################
####### User segmentation #######
#################################


def get_users_by_residence(accounts):
    """
    Returns a dictionary with the number of users
    by state and country
    """
    # Get summary table
    df = accounts.groupby(['Country', 'State']).size()
    # Get all countries
    countries = accounts['Country'].unique()
    # Create an empty dictionary
    users_by_residence = list()
    users_by_residence_detail = dict()
    # Build dictionary
    for country in countries:
        users_by_residence.append({
            'name': country,
            'y': sum([item for item in df[country]])
        })
        users_by_residence_detail[country] = dict(df[country])
    return {
        'detail': users_by_residence_detail,
        'global': users_by_residence
    }


def get_users_by_legal_docs(accounts):
    """
    Returns the number of users by legal docs
    """
    natural = (accounts['Legal_Docs'].fillna('0') == '0').sum()
    return [
        { 'name': 'Natural', 'y': natural },
        { 'name': 'Jurídica', 'y': len(accounts) - natural }
    ]


def get_users_by_gender(accounts):
    """
    Returns number of users by gender
    """
    return [
        { 'name': 'Masculinos', 'y': len(accounts[accounts['Gender'] == Account.GENDER_MALE]) },
        { 'name': 'Femeninos', 'y': len(accounts[accounts['Gender'] == Account.GENDER_FEMALE]) },
        { 'name': 'Neutros', 'y': len(accounts[accounts['Gender'] == Account.GENDER_NEUTRAL]) },
    ]


def get_users_by_age(accounts):
    """
    Returns number of users by age
    """
    return [
        { 'name': '18 a 25', 'y': len(accounts[(accounts['Age'] >= 18) & (accounts['Age'] <= 25)]) },
        { 'name': '26 a 35', 'y': len(accounts[(accounts['Age'] > 25) & (accounts['Age'] <= 35)]) },
        { 'name': '36 a 45', 'y': len(accounts[(accounts['Age'] > 35) & (accounts['Age'] <= 45)]) },
        { 'name': 'Más de 45', 'y': len(accounts[(accounts['Age'] > 45)]) },
    ]


def get_clients_by_commercial_sector():
    """
    Returns the number of clients by commercial sector
    """
    clients = get_clients_dataframe(Client.objects.all()) # pylint: disable=no-member
    df = clients.groupby(['Commercial_Sector']).size()
    sectors = clients['Commercial_Sector'].unique()
    clients_by_commercial_sector = list()
    for sector in sectors:
        clients_by_commercial_sector.append({
            'name': sector,
            'y': df[sector]
        })
    return clients_by_commercial_sector


#################################
#### Statistics by Category #####
#################################


def get_statistics_by_category():
    """
    Merge all dataframes returned by each category function
    Returns a DataFrame with number of partners, mean cost,
    number of requests, total profit and average duration,
    all by category
    """
    ALL_PARTNERS = Partner.objects.all() # pylint: disable=no-member
    ALL_REQUESTS = Request.objects.all() # pylint: disable=no-member
    ALL_DONE_REQUESTS = Request.objects.filter(status=Request.STATUS_DONE) # pylint: disable=no-member
    ALL_CATEGORY_NAMES = [category.name for category in Category.objects.all()] # pylint: disable=no-member
    
    partners = get_partners_by_category(ALL_PARTNERS, ALL_CATEGORY_NAMES)
    mean_costs = get_mean_costs_by_category(ALL_DONE_REQUESTS, ALL_CATEGORY_NAMES)
    duration = get_average_duration_by_category(ALL_DONE_REQUESTS, ALL_CATEGORY_NAMES)
    profit = get_average_profit_by_category(ALL_DONE_REQUESTS, ALL_CATEGORY_NAMES)
    status = get_requests_status_by_category(ALL_REQUESTS, ALL_CATEGORY_NAMES)
    df1 = pd.merge(partners, mean_costs, how='inner', on=['category'])
    df2 = pd.merge(duration, profit, how='inner', on=['category'])
    df3 = pd.merge(df1, df2, how='inner', on=['category'])
    df4 = pd.merge(df3, status, how='inner', on=['category'])
    category_table = list()
    for i in range(0, len(df4)):
        category_table.append({
            'category': df4.iloc[i]['category'],
            'partners': df4.iloc[i]['partners'],
            'mean_costs': df4.iloc[i]['mean_costs'],
            'duration_hs': df4.iloc[i]['duration_hs'],
            'profit': df4.iloc[i]['profit'],
            'requests_todo': df4.iloc[i]['requests_todo'][0] if type(df4.iloc[i]['requests_todo']) == tuple else df4.iloc[i]['requests_todo'],
            'requests_in_progress': df4.iloc[i]['requests_in_progress'][0] if type(df4.iloc[i]['requests_in_progress']) == tuple else df4.iloc[i]['requests_in_progress'],
            'requests_closed': df4.iloc[i]['requests_closed'][0] if type(df4.iloc[i]['requests_closed']) == tuple else df4.iloc[i]['requests_closed'],
            'requests_canceled': df4.iloc[i]['requests_canceled'][0] if type(df4.iloc[i]['requests_canceled']) == tuple else df4.iloc[i]['requests_canceled'],    
        })
    return category_table

def get_partners_by_category(partners, category_names):
    """
    Returns the number of partners by category
    """
    
    partner_category = dict()
    
    def sum_category(array, d=partner_category):
        for item in array:
            if item in d:
                d[item] += 1
            else:
                d[item] = 1
        return d
    
    for partner in partners:
        partner_category = sum_category(list(set([field.category for field in partner.know_fields])))
    all_categories = [field.category for partner in partners for field in partner.know_fields]
    all_categories_by_partner = list()
    for category in category_names:
        try:
            all_categories_by_partner.append([category, partner_category[category]])
        except KeyError:
            all_categories_by_partner.append([category, 0])
    return pd.DataFrame(all_categories_by_partner, columns=['category', 'partners'])


def get_mean_costs_by_category(done_requests, category_names):
    """
    Returns the mean cost by category
    """
    all_requests_costs = list()
    for request in done_requests:
        categories = list(set([field.category for field in request.know_fields]))
        for category in categories:
            all_requests_costs.append([category, float(request.price)])
    all_costs_by_category_dict = dict(pd.DataFrame(all_requests_costs, columns=['category','price']).groupby('category').mean()['price'])
    all_costs_by_category = list()
    for category in category_names:
        try:
            all_costs_by_category.append([category, all_costs_by_category_dict[category]])
        except KeyError:
            all_costs_by_category.append([category, 0.0])
    return pd.DataFrame(all_costs_by_category, columns=['category', 'mean_costs'])


def get_average_duration_by_category(done_requests, category_names):
    """
    Returns the average duration by category
    """
    all_done_requests_duration = list()
    for request in done_requests:
        categories = list(set([field.category for field in request.know_fields]))
        for category in categories:
            all_done_requests_duration.append([category, (request.date_closed - request.date_started).total_seconds()])
    duration = pd.DataFrame(all_done_requests_duration, columns=['category','duration'])
    duration['duration'] = duration['duration'] / 3600
    duration_by_category_dict = dict(round(duration.groupby('category').mean()['duration'], 2))
    duration_by_category = list()
    for category in category_names:
        try:
            duration_by_category.append([category, duration_by_category_dict[category]])
        except KeyError:
            duration_by_category.append([category, 0.0])
    return pd.DataFrame(duration_by_category, columns=['category', 'duration_hs'])


def get_average_profit_by_category(done_requests, category_names):
    """
    Returns the average profit by category
    """
    all_done_requests_profit = list()
    for request in done_requests:
        categories = list(set([field.category for field in request.know_fields]))
        for transaction in request.transactions:
            if (transaction.operation == Transaction.OP_ASILINKS_FEE) or ((transaction.operation == Transaction.OP_SPONSOR_FEE) and (transaction.receiver == Account.default_sponsor_account())):
                request_transaction = float(transaction.amount)
        for category in categories:
            all_done_requests_profit.append([category, request_transaction])
    profit = pd.DataFrame(all_done_requests_profit, columns=['category','profit'])
    profit_by_category_dict = dict(round(profit.groupby('category').mean()['profit'], 2))
    profit_by_category = list()
    for category in category_names:
        try:
            profit_by_category.append([category, profit_by_category_dict[category]])
        except KeyError:
            profit_by_category.append([category, 0.0])
    return pd.DataFrame(profit_by_category, columns=['category', 'profit'])


def get_requests_status_by_category(requests, category_names):
    """
    Returns the number of requests by status by category
    """
    
    def check_available(dataframe, category, status):
        try:
            return dataframe[category][status],
        except:
            return 0
          
    all_requests_status = list()
    for request in requests:
        categories = list(set([field.category for field in request.know_fields]))
        for category in categories:
            all_requests_status.append([category, request.status])

    status = pd.DataFrame(all_requests_status, columns=['category','status'])
    status['status'] = status['status'].map({
        1: 'STATUS_TODO',
        2: 'STATUS_IN_PROGRESS',
        3: 'STATUS_IN_PROGRESS',
        4: 'STATUS_IN_PROGRESS',
        5: 'STATUS_DONE',
        6: 'STATUS_CANCELED',
        7: 'STATUS_IN_PROGRESS'
    })
    requests_by_status_df = status.groupby(['category', 'status']).size()
    requests_by_status = list()
    for category in category_names:
        try:
            requests_by_status.append([
                category,
                check_available(requests_by_status_df, category, 'STATUS_TODO'),
                check_available(requests_by_status_df, category, 'STATUS_IN_PROGRESS'),
                check_available(requests_by_status_df, category, 'STATUS_DONE'),
                check_available(requests_by_status_df, category, 'STATUS_CANCELED'),
            ])
        except KeyError:
            requests_by_status.append([category, 0, 0, 0, 0])
    return pd.DataFrame(requests_by_status, columns=['category', 'requests_todo', 'requests_in_progress', 'requests_closed', 'requests_canceled'])
