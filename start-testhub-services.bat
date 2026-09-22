@echo off
rem TestHub execution service bootstrap (Redis + Celery Worker)
rem This is the entry point used by Task Scheduler for auto-start.
powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\86150\Doubao\chats\2026-09-15\new-chat-1\testhub_platform-main\start-testhub-services.ps1"
