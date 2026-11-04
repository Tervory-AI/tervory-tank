"""Real pinned-Django WSGI smoke, with synthetic settings/auth and no database.

The connector runs this in a separate subprocess so Django's global settings do
not affect Tank tests. Django belongs to the CRM image, not Tank requirements.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip('django', reason='Run with the pinned CRM Django runtime for WSGI smoke')

SCRIPT = r'''
import json,sys,types
from types import SimpleNamespace
from uuid import UUID
from django.urls import path
from django.http import JsonResponse
org='00000000-0000-0000-0000-000000000014'
settings=types.ModuleType('crm.settings')
settings.SECRET_KEY='dummy-crm-test-key'
settings.DEBUG=False
settings.ALLOWED_HOSTS=['testserver']
settings.ROOT_URLCONF='offline_urls'
settings.MIDDLEWARE=['offline_auth.Resolve']
settings.INSTALLED_APPS=[]
crm=types.ModuleType('crm');crm.__path__=[]
sys.modules['crm']=crm;sys.modules['crm.settings']=settings
state={'views':0}
def view(request):
    state['views']+=1
    return JsonResponse({'results':[]})
urls=types.ModuleType('offline_urls');urls.urlpatterns=[path('api/contacts/',view)]
sys.modules['offline_urls']=urls
auth=types.ModuleType('offline_auth')
class Resolve:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        request.org=SimpleNamespace(id=UUID(org))
        request._pat=object() if sys.argv[2]=='pat' else None
        return self.get_response(request)
auth.Resolve=Resolve;sys.modules['offline_auth']=auth
import tervory_connector_wsgi
from django.test import RequestFactory
kw={} if sys.argv[1]=='missing' else {'HTTP_X_TERVORY_CRM_ORGANIZATION':sys.argv[1]}
environ=RequestFactory().get('/api/contacts/',**kw).environ
captured={}
def start(status,headers):captured.update(status=status,headers=dict(headers))
body=b''.join(tervory_connector_wsgi.application(environ,start))
print(json.dumps({'status':int(captured['status'].split()[0]),'org':captured['headers'].get('X-Tervory-CRM-Organization'),'views':state['views']}))
'''


@pytest.mark.parametrize('expected,pat,status,views',[
    ('00000000-0000-0000-0000-000000000014','pat',200,1),
    ('00000000-0000-0000-0000-000000000012','pat',403,0),
    ('00000000-0000-0000-0000-000000000014','no-pat',403,0),
    ('missing','no-pat',200,1),
])
def test_real_wsgi_initialization_and_binding(expected,pat,status,views):
    root=Path(__file__).parents[1]
    env={**os.environ,'PYTHONPATH':str(root/'ops/trigger-crm'),'DJANGO_SETTINGS_MODULE':'crm.settings'}
    result=subprocess.run([sys.executable,'-c',SCRIPT,expected,pat],env=env,capture_output=True,text=True,check=True,timeout=20)
    proof=json.loads(result.stdout)
    assert proof['status']==status and proof['views']==views
    if status==200 and pat=='pat':assert proof['org']==expected
    else:assert proof['org'] is None
