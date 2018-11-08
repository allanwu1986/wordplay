'''
Created on Mar 9, 2018

@author: alice
'''
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from word2description.models import Word, Description

class Command(BaseCommand):
    pos_dict = {
        'n': Word.NOUN,
        'v': Word.VERB,
        'adj': Word.ADJ,
        'adv': Word.ADV}
    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            dest='file',
            help='Add words from a file'
            )
        parser.add_argument(
            '--username',
            dest='username',
            help='User who creted this description.'
            )

    def handle(self, *args, **options):
        try:
            input_file = open(options['file'], 'r')
            user = get_user_model().objects.get(username=options['username'])
            for line in input_file:
                word = line.strip().split('\t')
                my_word = Word.objects.create(word=word[0], pos=self.pos_dict[word[1]])
                Description.objects.create(prompt=my_word, description=word[2], writer=user)
        except KeyError:
            pass