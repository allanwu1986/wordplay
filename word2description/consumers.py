'''
Created on Mar 4, 2018

@author: alice
'''
from django.conf import settings
from django.db.models import Sum

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async

from .models import Game, Word, Description, DescriptionWithGame, Answer, GamePool, Questioner, Answerer

from threading import Lock

@database_sync_to_async
def create_game(questioner_channel_name):
    new_game = Game.objects.create(questioner=questioner_channel_name)
    return new_game

@database_sync_to_async
def get_game(questioner_channel_name, answerer_channel_name):
    game = Game.objects.get(questioner=questioner_channel_name)
    game.answerer = answerer_channel_name
    game.save()
    return game

@database_sync_to_async
def set_game_to_finished(game):
    #game = Game.objects.get(pk=game_id)
    game.finished = True
    game.save()

word_index = -1
word_index_lock = Lock()

@database_sync_to_async
def select_next_word():
    global word_index
    global word_index_lock
    word_index_lock.acquire()
    try:
        word_index = (word_index + 1) % Word.objects.count()
        word = Word.objects.get(pk=word_index+1)
    finally:
        word_index_lock.release()
    return word

@database_sync_to_async
def record_description(word, word_description, writer, game):
    description = Description.objects.create(
        prompt=word,
        description=word_description,
        writer=writer)
    return DescriptionWithGame.objects.create(
        description=description,
        game=game)

@database_sync_to_async
def get_description(description_id):
    description_with_game = DescriptionWithGame.objects.get(pk=description_id)
    description = description_with_game.description
    return description, description_with_game

@database_sync_to_async
def get_word(description):
    return description.prompt

@database_sync_to_async
def refresh_model(model):
    model.refresh_from_db()
    return model

@database_sync_to_async
def record_answer(answer, score, description, writer):
    return Answer.objects.create(
        answer=answer,
        score=score,
        description=description,
        writer=writer)

@database_sync_to_async
def get_first_description(game):
    description_with_game = game.descriptionwithgame_set.first()
    if description_with_game == None:
        return None, None
    description = description_with_game.description
    return description, description_with_game

class QuestionerConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
        else:
            await self.accept()

    async def receive_json(self, content):
        try:
            command = content["command"]
            if command == "send":
                await self.receive_question(content)
            elif command == "join":
                await self.enter_game()
            elif command == "leave":
                await self.leave_game()
        except KeyError as e:
            await self.send_json({"error": str(e)},)
        except AttributeError as e:
            await self.send_json({"error": str(e)},)

    async def enter_game(self):
        self.questioner = self.scope["user"].__copy__()
        self.answerer_channel = ""
        self.game = await create_game(self.channel_name)
        await self.send_json({
            "join": str(1),
            "title": "Game"
            },)
        await self.questioner_prompt({
            "msg_type": settings.MSG_TYPE_ENTER
            })

    async def receive_question(self, content):
        description_with_game = await record_description(
            self.word,
            content["message"],
            self.questioner,
            self.game)
        await self.send_json({
            "msg_type": settings.MSG_TYPE_WAIT,
            "message": "Waiting for a response...",
            "room": str(1)
            },)
        if self.answerer_channel != "":
            channel_name = self.answerer_channel
        else:
            await refresh_model(self.game)
            channel_name = self.game.answerer
        if channel_name != "":
            channel_layer = get_channel_layer()
            await channel_layer.send(channel_name, {
                "type": "answerer.ask",
                "description_id": description_with_game.pk,
                })
        else:
            await self.send_json({
                "msg_type": settings.MSG_TYPE_WAIT,
                "message": "This might take a long time because we haven't found a partner to play with you...",
                "room": str(1)
                },)

    async def leave_game(self):
        await self.send_json({
            "msg_type": settings.MSG_TYPE_LEAVE,
            "leave": str(1),
        },)
        try:
            await set_game_to_finished(self.game)
        except AttributeError:
            pass

    async def questioner_prompt(self, event):
        self.word = await select_next_word()
        msg_type = event["msg_type"]
        msg_template = ""
        if msg_type == settings.MSG_TYPE_ENTER:
            msg_template = "Welcome to the game! To start, enter a description for the word \"%s\"."
        elif msg_type == settings.MSG_TYPE_PROMPT:
            if event["score"] > 0.0:
                scored = "Congratulations, your partner guessed your word right!\n"
            else:
                scored = "Sorry, your partner did not guess your word.\n"
            msg_template = scored+"To continue, describe the word \"%s\"."
        await self.send_json({
            "msg_type": msg_type,
            "message": msg_template % self.word.word,
            "room": str(1)
        },)

    async def disconnect(self, code):
        await self.leave_game()
        #await set_game_to_finished(self.game.pk)

@database_sync_to_async
def no_answerer(n):
    return list(Game.objects.filter(answerer="").order_by('start')[:n])

@database_sync_to_async
def get_first_game(channel_name):
    game = Game.objects.filter(answerer="", finished=False).order_by('start').first()
    if game != None:
        game.answerer = channel_name
        game.save()
    return game

class AnswererConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
        else:
            await self.accept()

    async def receive_json(self, content):
        try:
            command = content["command"]
            if command == "send":
                await self.receive_answer(content)
            elif command == "join":
                await self.enter_game()
            elif command == "leave":
                await self.leave_game()
        except KeyError as e:
            await self.send_json({"error": str(e)},)
        except AttributeError as e:
            await self.send_json({"error": str(e)},)

    async def enter_game(self):
        self.questioner_channel = ""
        self.answerer = self.scope["user"].__copy__()
        self.game = await get_first_game(self.channel_name)
        #get_game(self.scope["url_route"]["args"][0], self.channel_name)
        await self.send_json({
            "join": str(1),
            "title": "Game"
            },)
        if self.game != None:
            self.description, self.description_with_game = await get_first_description(self.game)
            if self.description != None:
                await self.answerer_ask({"description_id": self.description_with_game.pk})
            else:
                await self.send_json({
                    "msg_type": settings.MSG_TYPE_ENTER,
                    "message": "Waiting for your partner to start...",
                    "room": str(1)
                    },)
        else:
            await self.send_json({
                "msg_type": settings.MSG_TYPE_ENTER,
                "message": "Trying to find a partner for you.",
                "room": str(1)
                },)

    async def receive_answer(self, content):
        if content["message"].strip() == self.word.word:
            score = 1.0
        else:
            score = 0.0
        if score > 1.0:
            plural = "s"
        else:
            plural = ""
        if score > 0.0:
            response = "Congratulations! You gained %f point%s." % (score, plural)
        else:
            response = "Sorry, that was the wrong answer."
        await record_answer(
            content["message"],
            score,
            self.description_with_game,
            self.answerer)
        await self.send_json({
            "msg_type": settings.MSG_TYPE_WAIT,
            "message": response+" Now waiting for the next question...",
            "room": str(1)
            },)
        channel_layer = get_channel_layer()
        if self.questioner_channel != "":
            channel_name = self.questioner_channel
        else:
            channel_name = (await refresh_model(self.game)).questioner
        await channel_layer.send(channel_name, {
            "type": "questioner.prompt",
            "score": score,
            "msg_type": settings.MSG_TYPE_PROMPT
            })

    async def leave_game(self):
        await self.send_json({
            "msg_type": settings.MSG_TYPE_LEAVE,
            "leave": str(1),
        },)
        try:
            await set_game_to_finished(self.game)
        except AttributeError:
            pass

    async def answerer_ask(self, event):
        self.description, self.description_with_game = await get_description(event["description_id"])
        self.word = await get_word(self.description)
        await self.send_json({
            "msg_type": settings.MSG_TYPE_QUESTION,
            "message": "What is the word for \"%s\"" % self.description.description,
            "room": str(1)
            },)

    async def disconnect(self, code):
        await self.leave_game()
        #await set_game_to_finished(self.game.pk)

gamepools = {"default": GamePool.objects.get(label='default')}

@database_sync_to_async
def get_gamepool(label):
    return GamePool.objects.get(label=label)

@database_sync_to_async
def add_questioner_to_pool(game, questioner, channel_name):
    return Questioner.objects.create(
        channel=channel_name,
        questioner=questioner,
        pool=game)

def none_to_zero(value):
    if value == None:
        return 0
    else:
        return value

@database_sync_to_async
def questioner_score(game, questioner):
    return none_to_zero(DescriptionWithGame.objects.filter(description__writer=questioner).aggregate(Sum('score'))['score__sum'])

@database_sync_to_async
def answerer_score(game, answerer):
    return none_to_zero(Answer.objects.filter(writer=answerer).aggregate(Sum('score'))['score__sum'])

@database_sync_to_async
def delete_model(model):
    model.delete()

class QuestionerPoolConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def receive_json(self, content):
        try:
            command = content["command"]
            if command == "send":
                await self.receive_question(content)
            elif command == "join":
                await self.enter_game()
            elif command == "leave":
                await self.leave_game()
        except KeyError as e:
            await self.send_json({"error": str(e)},)
        except AttributeError as e:
            await self.send_json({"error": str(e)},)

    async def enter_game(self):
        self.questioner = self.scope["user"].__copy__()
        self.answerer_channel = ""
        self.game = gamepools["default"]
        self.pool_info = await add_questioner_to_pool(
            self.game, self.questioner, self.channel_name)
        total_score = await questioner_score(self.game, self.questioner)
        total_score += await answerer_score(self.game, self.questioner)
        await self.send_json({
            "join": str(1),
            "title": "Enter new definition",
            "score": total_score,
            },)
        await self.questioner_prompt({
            "msg_type": settings.MSG_TYPE_ENTER
            })

    async def receive_question(self, content):
        await record_description(
            self.word,
            content["message"],
            self.questioner,
            self.game)
        await self.questioner_prompt({
            "msg_type": settings.MSG_TYPE_PROMPT
            })

    async def leave_game(self):
        try:
            await delete_model(self.pool_info)
        except Exception:
            pass
        await self.send_json({
            "msg_type": settings.MSG_TYPE_LEAVE,
            "leave": str(1),
        },)

    async def questioner_prompt(self, event):
        self.word = await select_next_word()
        msg_type = event["msg_type"]
        msg_template = ""
        if msg_type == settings.MSG_TYPE_ENTER:
            msg_template = """Thanks for your participation! You will be describing a series of words.
            Start by describing \"%s\"."""
        elif msg_type == settings.MSG_TYPE_PROMPT:
            msg_template = "Describe the word \"%s\"."
        await self.send_json({
            "msg_type": msg_type,
            "message": msg_template % self.word.word,
            "room": str(1)
        },)

    async def questioner_score(self, event):
        await self.send_json({
            "msg_type": settings.MSG_TYPE_SCORE,
            "score": event["score"],
            "room": str(1)},)

    async def disconnect(self, code):
        await self.leave_game()

description_index = -1
descri_index_lock = Lock()
gamepool_descriptions = []

@database_sync_to_async
def get_next_description_in_gamepool(gamepool):
    global description_index
    global descri_index_lock
    #global gamepool_descriptions
    descriptions = gamepool.descriptionwithgame_set
    #length = len(gamepool_descriptions)
    #if length == 0 or description_index + 1 == length and length != descriptions.count():
    #    gamepool_descriptions = list(descriptions)
    descri_index_lock.acquire()
    try:
        description_index = (description_index + 1) % descriptions.all().count()
        description_with_game = descriptions.all()[description_index]
    finally:
        descri_index_lock.release()
    return description_with_game.description.prompt, description_with_game.description, description_with_game, description_with_game.description.writer

@database_sync_to_async
def add_answerer_to_pool(game, answerer, channel_name):
    return Answerer.objects.create(
        channel=channel_name,
        answerer=answerer,
        pool=game)

@database_sync_to_async
def add_score_to_description_writer(gamepool, description_with_game, score):
    #description_with_game.update(score=F('score') + score)
    description_with_game.score += score
    description_with_game.save()
    writer = description_with_game.description.writer
    questioners = gamepool.questioner_set.all().filter(questioner=writer)
    channels = []
    for q in questioners:
        channels.append(q.channel)
    return channels

class AnswererPoolConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def receive_json(self, content):
        try:
            command = content["command"]
            if command == "send":
                await self.receive_answer(content)
            elif command == "join":
                await self.enter_game()
            elif command == "leave":
                await self.leave_game()
        except KeyError as e:
            await self.send_json({"error": str(e)},)
        except AttributeError as e:
            await self.send_json({"error": str(e)},)

    async def enter_game(self):
        self.questioner_channel = ""
        self.answerer = self.scope["user"].__copy__()
        self.game = gamepools["default"]
        #get_game(self.scope["url_route"]["args"][0], self.channel_name)
        self.pool_info = await add_answerer_to_pool(
            self.game, self.answerer, self.channel_name)
        total_score = await answerer_score(self.game, self.answerer)
        total_score += await questioner_score(self.game, self.answerer)
        await self.send_json({
            "join": str(1),
            "title": "Guess the word",
            "score": total_score,
            },)
        await self.answerer_ask()

    async def receive_answer(self, content):
        if content["message"].strip() == self.word.word:
            score = 1.0
        else:
            score = 0.0
        if score > 1.0:
            plural = "s"
        else:
            plural = ""
        if self.description_writer.pk == self.answerer.pk:
            answerer_self = True
            score = 0.0
        else:
            answerer_self = False
        if answerer_self:
            response = "You answered your own description, which gained you no points."
        elif score > 0.0:
            response = "Congratulations! You gained %f point%s." % (score, plural)
        else:
            response = "Sorry, that was the wrong answer."
        await record_answer(
            content["message"],
            score,
            self.description_with_game,
            self.answerer)
        await self.send_json({
            "msg_type": settings.MSG_TYPE_WAIT,
            "message": response,
            "score": score,
            "room": str(1)
            },)
        
        description_writer_score = score * 2
        channels = await add_score_to_description_writer(
            self.game, self.description_with_game, description_writer_score)
        channel_layer = get_channel_layer()
        for channel in channels:
            await channel_layer.send(channel, {
                "type": "questioner.score",
                "score": description_writer_score})
        
        await self.answerer_ask()

    async def leave_game(self):
        try:
            await delete_model(self.pool_info)
        except Exception:
            pass
        await self.send_json({
            "msg_type": settings.MSG_TYPE_LEAVE,
            "leave": str(1),
        },)

    async def answerer_ask(self):
        self.word, self.description, self.description_with_game, self.description_writer = await get_next_description_in_gamepool(self.game)
        await self.send_json({
            "msg_type": settings.MSG_TYPE_QUESTION,
            "message": "What is the word for \"%s\"?" % self.description.description,
            "room": str(1)
            },)

    async def disconnect(self, code):
        await self.leave_game()
