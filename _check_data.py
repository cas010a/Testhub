# -*- coding: utf-8 -*-
import os, sys, json, urllib.request
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django
django.setup()
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='admin')
TOKEN = str(RefreshToken.for_user(u).access_token)

req = urllib.request.Request(
    'http://localhost:8000/api/requirement-analysis/testcase-generation/TASK_0265C446/',
    headers={'Authorization': f'Bearer {TOKEN}'},
)
with urllib.request.urlopen(req, timeout=15) as resp:
    data = json.loads(resp.read().decode('utf-8'))

print('顶层 keys:', list(data.keys())[:20])
for key in ('test_cases', 'final_test_cases', 'cases'):
    if key in data:
        v = data[key]
        print(f'{key} 类型: {type(v).__name__}', '长度:', len(v) if hasattr(v, '__len__') else '-')
        if isinstance(v, list) and v:
            print('  首个:', json.dumps(v[0], ensure_ascii=False)[:250])
            print('  次个:', json.dumps(v[1], ensure_ascii=False)[:150])
        break
