#!/bin/bash

python3 manage.py makemigrations app

python3 manage.py makemigrations

python3 manage.py migrate

export DJANGO_SETTINGS_MODULE=game2.settings
exec daphne -p 8000 -b 0.0.0.0 game2.asgi:application