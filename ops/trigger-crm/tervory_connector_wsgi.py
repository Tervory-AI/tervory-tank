"""Use the pinned BottleCRM app with a final organization-binding middleware."""
import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')
_middleware = 'tervory_crm_middleware.OrganizationBinding'
if _middleware not in settings.MIDDLEWARE:
    settings.MIDDLEWARE = [*settings.MIDDLEWARE, _middleware]
application = get_wsgi_application()
