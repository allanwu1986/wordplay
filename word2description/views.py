'''
Created on Mar 12, 2018

@author: alice
'''
from datetime import datetime
from dateutil import parser

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.http import HttpResponseRedirect

class Room:
    def __init__(self, identifier, title):
        self.id = identifier
        self.title = title
    def __str__(self):
        return self.title

@login_required
def index(request):
    """
    Root page view. This is essentially a single-page app, if you ignore the
    login and admin parts.
    """
    # Get a list of rooms, ordered alphabetically

    # Render that in the index template
    return render(request, "index.html",
                  {"questions": [Room(1, "Play as Questioner")],
                   "answers": [Room(1, "Play as Answerer")]})

@login_required
def pool(request):
    try:
        parser.parse(request.user.username)
        signed_up = False
    except ValueError:
        signed_up = True
    request.signed_up = signed_up
    return render(request, "pool.html", {"signed_up": signed_up})

def auto_login(request):
    u = request.user
    if (not u.is_authenticated) or (not u.is_active):
        placeholder = datetime.utcnow().isoformat()
        user = get_user_model().objects.create_user(
            username=placeholder,
            password=placeholder)
        login(request, user)
    return HttpResponseRedirect('/pool/')

def reset_password(request):
    u = request.user
    try:
        if (not u.is_authenticated) or (not u.is_active):
            username = request.POST["username"]
            password = request.POST["password"]
            u.username = username
            u.save()
            u.set_password(password)
        return HttpResponseRedirect('/pool/')
    except KeyError:
        return render(request, "change_password.html", {})
