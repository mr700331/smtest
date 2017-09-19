# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.http import HttpResponse
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
import requests
import datetime

class FirstWorkingEmailBackend(BaseEmailBackend):
    def __init__(self, *args, **kwargs):
        super(FirstWorkingEmailBackend, self).__init__(*args, **kwargs)
        self._connection = None

    def open(self):
        if self._connection:
            return False
        backend_name = find_first_working_backend()
        self._connection = get_connection(backend_name, fail_silently=self.fail_silently)
        return True

    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None

    def send_messages(self, email_messages):
        created_connection = self.open()
        try:
            return self._connection.send_messages(email_messages)
        finally:
            if created_connection:
                self.close()

ESP_STATUS_APIS = {
    'anymail.backends.mailgun.MailgunBackend': {
        'url': 'http://status.mailgun.com/api/v2/summary.json',
        'json_path': 'status.indicator',
        'up_value': 'none',
        'components_url': 'http://status.mailgun.com/api/v2/components.json',
        'components_to_check': [
            'Outbound Delivery',
        ],
        'component_up_value': 'operational',
    },
    'anymail.backends.sendgrid.SendGridBackend': {
        'url': 'http://status.sendgrid.com/api/v2/summary.json',
        'json_path': 'incidents',
        'up_value': [],
        'components_url': 'http://status.sendgrid.com/api/v2/components.json',
        'components_to_check': [
            'Mail Sending',
            'API',
        ],
        'component_up_value': 'operational',
    },
}

CACHE_KEY = 'current_working_email_backend'
DEFAULT_CACHE_TIMEOUT = 60*60  # seconds

def invalidate_current_working_email_backend(request):
    """View function to be used as ESP status page webhook"""
    cache.delete(CACHE_KEY)
    return HttpResponse()

def find_first_working_backend():
    """Returns the first email backend whose status API returns OK, else raises RuntimeError

    Uses cached value if available.
    """
    backend = cache.get(CACHE_KEY)
    if backend is None:
        try:
            backends = settings.FIRST_WORKING_EMAIL_BACKENDS
            cache_timeout = settings.get('FIRST_WORKING_EMAIL_CACHE_TIMEOUT', DEFAULT_CACHE_TIMEOUT)
        except AttributeError:
            raise ImproperlyConfigured("Set FIRST_WORKING_EMAIL_BACKENDS to a list of possible backends")
        for possible_backend in backends:
            if is_backend_working(possible_backend):#could be changed to is_component_working
                backend = possible_backend
                break
        if backend is None:
            raise RuntimeError("No currently working backend among %s" % ', '.join(backends))
        elif cache_timeout:
            cache.set(CACHE_KEY, backend)
    return backend

def is_backend_working(backend):
    try:
        status_api = ESP_STATUS_APIS[backend]
    except KeyError:
        raise ImproperlyConfigured("Don't know how to check ESP %r is working; "
                                   "add it to ESP_STATUS_APIS " % backend)
    try:
        response = requests.get(status_api['url'])
        response.raise_for_status()
        json = response.json()
    except (requests.RequestException, ValueError):
        return False  # status API down, error, or non-json response

    status = json_path(json, status_api['json_path'])
    return status == status_api['up_value']

def is_component_working(backend):
    try:
        status_api = ESP_STATUS_APIS[backend]
    except KeyError:
        raise ImproperlyConfigured("Don't know how to check ESP %r is working; "
                                   "add it to ESP_STATUS_APIS " % backend)
    try:
        response = requests.get(status_api['url'])
        response.raise_for_status()
        json = response.json()
    except (requests.RequestException, ValueError):
        return False  # status API down, error, or non-json response

    for component in json['components']:
        if component['name'] in status_api['components_to_check'] and component['status'] != status_api['component_up_value']:
            return False

    return True #all components are up, component no longer exists, or ESP has changed their statuspage

def json_path(json, path, default=None):
    """Given path='p1.p2', returns json['p1']['p2'], or default if not there"""
    # (You could switch this to something like pyjq for more flexibility)
    try:
        result = json
        for segment in path.split('.'):
            result = result[segment]
        return result
    except KeyError:
        return default

def send_mail(r):
    from django.core.mail import send_mail
    from anymail.message import AnymailMessage

    to="mrakowski@zortel.pl"
    if 'to' in r.GET:
	to=r.GET['to']

    print("to=" + to)
    message = AnymailMessage(
    subject="Welcome",
    body="Welcome SNACC",
    to=[to],
    tags=["Onboarding"],  # Anymail extra in constructor
    )    
    message.open_tracking = True
    message.send()
    print("status=" + repr(message.anymail_status))
    print("id=" + message.anymail_status.message_id)
    print(repr(message.anymail_status.recipients))
    print r.GET.keys()
    print("====")
#    send_mail("Subject", "text body", "mrak@zortel.pl",
#                      [to], html_message="<html>html body</html>")
    
# Create your views here.
def current_datetime(request):
    now = datetime.datetime.now()
    html = "<html><body>It is now %s.</body></html>" % now
    send_mail(request)
    return HttpResponse(html)


from anymail.signals import tracking
from django.dispatch import receiver

@receiver(tracking)  # add weak=False if inside some other function/class
def handle_bounce(sender, event, esp_name, **kwargs):
    if event.event_type == 'bounced':
        print("Message %s to %s bounced" % ( event.message_id, event.recipient))

@receiver(tracking)
def handle_click(sender, event, esp_name, **kwargs):
    if event.event_type == 'clicked':
        print("Recipient %s clicked url %s" % ( event.recipient, event.click_url))

