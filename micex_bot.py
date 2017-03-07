# coding: utf8
import json
import os
import re
import sys
import urllib

import requests

from flask import Flask
from flask import request

from raven.contrib.flask import Sentry

app = Flask(__name__)
sentry = Sentry(app)

_TOKEN = os.environ.get('TELEGRAM_API_TOKEN')
_API_PREFIX = 'https://api.telegram.org/bot'
_API = _API_PREFIX + _TOKEN
_WEB_HOOK = os.environ.get('WEBHOOK_HOSTNAME') + urllib.quote_plus(_TOKEN)
_MICEX_USDRUB_URL = 'http://www.micex.ru/issrpc/marketdata/currency/selt/daily/preview/result.json?collection_id=173&board_group_id=13'
_YAHOO_FINANCE_RUBKRW_URL = 'https://query.yahooapis.com/v1/public/yql?q=SELECT%20*%20FROM%20yahoo.finance.xchange%20WHERE%20pair%3D%22RUBKRW%22%20%7C%20truncate(count%3D1)&format=json&env=store%3A%2F%2Fdatatables.org%2Falltableswithkeys&callback='
_YAHOO_FINANCE_KRWRUB_URL = 'https://query.yahooapis.com/v1/public/yql?q=SELECT%20*%20FROM%20yahoo.finance.xchange%20WHERE%20pair%3D%22KRWRUB%22%20%7C%20truncate(count%3D1)&format=json&env=store%3A%2F%2Fdatatables.org%2Falltableswithkeys&callback='
_YAHOO_FINANCE_USDKRW_URL = 'https://query.yahooapis.com/v1/public/yql?q=SELECT%20*%20FROM%20yahoo.finance.xchange%20WHERE%20pair%3D%22USDKRW%22%20%7C%20truncate(count%3D1)&format=json&env=store%3A%2F%2Fdatatables.org%2Falltableswithkeys&callback='


def set_webhook():
    headers = {'Content-Type': 'application/json'}
    r = requests.post(_API + '/setWebhook',
        data=json.dumps({'url': _WEB_HOOK}),
        headers=headers)
    sys.stderr.write('Webhook status: {0}: {1}'.format(r.status_code, r.text))


def send_yahoo_finance_krw_data(to, base):
    if to is None:
        sys.stderr.write('Cannot find chat_id\n')
    if base == 'rub':
        r = requests.get(_YAHOO_FINANCE_RUBKRW_URL)
    elif base == 'usd':
        r = requests.get(_YAHOO_FINANCE_USDKRW_URL)
    elif base == 'kilokrw':
        r = requests.get(_YAHOO_FINANCE_KRWRUB_URL)
    else:
        r = requests.get(_YAHOO_FINANCE_USDKRW_URL)
    sys.stderr.write('Yahoo reply {0}: {1}\n'.format(r.status_code, r.text))
    data = json.loads(r.text.decode('utf-8'))
    reply = data.get('query', {}).get('results', {}).get('rate', {})
    if base == 'kilokrw':
        reply['Rate'] = 1000 * float(reply['Rate'])
        reply['Ask'] = 1000 * float(reply['Ask'])
        reply['Bid'] = 1000 * float(reply['Bid'])
        reply['Name'] = '1000' + reply['Name']
    message = 'Инструмент: {Name}: {Rate},\n'\
              'Спрос: {Ask}, Предложение: {Bid},\n'\
              'Последнее обновление {Date} {Time},\n\n'.format(**reply)

    headers = {'Content-Type': 'application/json'}
    r = requests.post(
        _API + '/sendMessage',
        data=json.dumps({'chat_id': to, 'text': message}),
        headers=headers)
    sys.stderr.write('Telegram sendMessage reply {0}: {1}'.format(
        r.status_code, r.text))


def send_micex_usdrub_data(to):

    usa_flag = u'\U0001f1fa\U0001f1f8'
    rub_sign = u'\u20bd'
    day_sign = u'\U0001f307'
    night_sign = u'\U0001f303'

    if to is None:
        sys.stderr.write('Cannot find chat_id\n')
    r = requests.get(_MICEX_USDRUB_URL)
    sys.stderr.write('MICEX reply {0}: {1}\n'.format(r.status_code, r.text))
    data = json.loads(r.text.decode('utf-8'))
    message = ''
    message_template = u'{FLAG_SIGN}{TOD_TOM_SIGN} {LAST}{MONEY_SIGN} {CHANGE_PCT}%{UP_OR_DOWN_SIGN}\n'
    for ticker in data:
        if isinstance(ticker, dict):

            name = ticker['SHORTNAME']
            if not ('_TOD' in name or '_TOM' in name):
                continue

            delta = ticker['CHANGE']
            value = ticker['LAST']

            ticker['TOD_TOM_SIGN'] = day_sign if 'TOD' in name else night_sign
            ticker['FLAG_SIGN'] = usa_flag
            ticker['MONEY_SIGN'] = rub_sign
            ticker['UP_OR_DOWN_SIGN'] = get_up_or_down_sign(delta)
            ticker['CHANGE_PCT'] = get_delta_in_percents(value, delta)
            ticker['LAST'] = '{0:.2f}'.format(value)

            msg = message_template.format(**ticker)
            message += msg
    headers = {'Content-Type': 'application/json'}
    r = requests.post(
        _API + '/sendMessage',
        data=json.dumps({'chat_id': to, 'text': message}),
        headers=headers)
    sys.stderr.write('Telegram sendMessage reply {0}: {1}'.format(
        r.status_code, r.text))


def get_delta_in_percents(value, delta):
    return '{0:.2f}'.format(100 * delta / (delta + value))


def get_up_or_down_sign(delta):

    upwards_arrow = u'\u2b06'
    downwards_arrow = u'\u2b07'

    if delta > 0:
        return upwards_arrow
    elif delta < 0:
        return downwards_arrow
    else:
        return ''


def parse_command(update):
    message = update.get('message', {}).get('text', '')
    match = re.match(
        '^/(?P<command>[^\s@]+)(?:@\S+\s)?(?P<inline_message>.*)?', message)
    if match is None:
        return None, None
    return match.group('command'), match.group('inline_message')


@app.route('/' + _TOKEN, methods=['POST'])
def web_hook():
    update = request.get_data()
    data = json.loads(update.decode('utf-8'))
    sys.stderr.write('Webhook received: {0}\n'.format(data))

    command, _ = parse_command(data)
    chat_id = data.get('message', {}).get('chat', {}).get('id')
    if command == 'usd':
        send_micex_usdrub_data(chat_id)
    elif command == 'rubikilowon':
        send_yahoo_finance_krw_data(chat_id, 'kilokrw')
        send_yahoo_finance_krw_data(chat_id, 'usd')
    elif command == 'usdkrw':
        send_yahoo_finance_krw_data(chat_id, 'usd')
    return 'OK'

if __name__ == '__main__':
    if not _TOKEN:
        sys.stderr.write('Telegram bot token not configured. Exiting.\n')
        sys.exit(status=-1)
    set_webhook()
    port = int(os.environ.get("PORT", 80))
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as exc:
        sys.stderr.write('{}\n'.format(exc))
