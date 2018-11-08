from django.db import models
from django.contrib.auth.models import User


class Word(models.Model):
    word = models.CharField(max_length=40)
    NOUN = 0
    VERB = 1
    ADJ = 2
    ADV = 3
    PART_OF_SPEECH = (
        (NOUN, 'Noun'),
        (VERB, 'Verb'),
        (ADJ, 'Adjective'),
        (ADV, 'Adverb'),
        )
    pos = models.IntegerField(choices=PART_OF_SPEECH)


class BaseGame(models.Model):
    start = models.DateTimeField(auto_now_add=True)
    end = models.DateTimeField(auto_now=True)
    finished = models.BooleanField(default=False)


class Game(BaseGame):
    questioner = models.CharField(default="", max_length=128)
    answerer = models.CharField(default="", max_length=128)


class GamePool(BaseGame):
    label = models.CharField(max_length=40)


class Questioner(models.Model):
    channel = models.CharField(max_length=128)
    questioner = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    pool = models.ForeignKey(GamePool, on_delete=models.DO_NOTHING)


class Answerer(models.Model):
    channel = models.CharField(max_length=128)
    answerer = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    pool = models.ForeignKey(GamePool, on_delete=models.DO_NOTHING)


class Description(models.Model):
    prompt = models.ForeignKey(Word, on_delete=models.DO_NOTHING)
    description = models.CharField(max_length=1024)
    timestamp = models.DateTimeField(auto_now_add=True)
    writer = models.ForeignKey(User, on_delete=models.DO_NOTHING)


class DescriptionWithGame(models.Model):
    description = models.ForeignKey(Description, on_delete=models.DO_NOTHING)
    game = models.ForeignKey(BaseGame, on_delete=models.DO_NOTHING)
    score = models.FloatField(default=0.0)


class Answer(models.Model):
    answer = models.CharField(max_length=40)
    score = models.FloatField(default=0.0)
    timestamp = models.DateTimeField(auto_now_add=True)
    writer = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    description = models.ForeignKey(DescriptionWithGame, on_delete=models.DO_NOTHING)


class Flag(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    comment = models.CharField(max_length=1024)
    complainer = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    description = models.ForeignKey(Description, on_delete=models.DO_NOTHING)
