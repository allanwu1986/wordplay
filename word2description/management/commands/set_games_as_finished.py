'''
Created on Mar 17, 2018

@author: alice
'''
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from word2description.models import Game


def parse_time(time_str):
    t = datetime.strptime(time_str,"%H:%M:%S")
    return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--inactive_period',
            dest='inactive_period',
            help='Set game to finished after an inactive period.'
            )

    def handle(self, *args, **options):
        try:
            inactive = parse_time(options['inactive_period'])
            Game.objects.filter(end__lte=datetime.utcnow()-inactive).update(finished=True)
        except KeyError:
            pass