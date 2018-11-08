'''
Created on Mar 19, 2018

@author: alice
'''
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from word2description.models import Description, DescriptionWithGame, GamePool

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            dest='username',
            help='Description created by this user to add to game.'
            )
        parser.add_argument(
            '--game',
            dest='game',
            help='Name of game to add description to.'
            )

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['username'])
            try:
                game = GamePool.objects.get(label=options['game'])
            except GamePool.DoesNotExist:
                game = GamePool.objects.create(label=options['game'])
            for description in Description.objects.filter(writer=user):
                DescriptionWithGame.objects.create(
                    description=description,
                    game=game)
        except KeyError:
            pass