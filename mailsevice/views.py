# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.http import HttpResponse
import datetime


def send_mail(r):
    from django.core.mail import send_mail
    from anymail.message import AnymailMessage

    to="you@example.com"
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

