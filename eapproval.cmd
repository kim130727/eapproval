@echo off

cd /d %~dp0

set DJANGO_SETTINGS_MODULE=config.settings.local

uv run manage.py runserver