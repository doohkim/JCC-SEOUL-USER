from django.contrib import admin
from django.urls import path

from config.urls._base import urlpatterns as base_urlpatterns
# from utils.logging import getLogger

# logger = getLogger(__name__)

admin.site.site_header = "JCC Seoul"

urlpatterns = base_urlpatterns + [
    path("", admin.site.urls),
]
