"""
URL configuration for config project.

The `urlpatterns` list routes views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from config.admin_legacy_redirect import (
    LEGACY_USERS_ADMIN_PATTERN,
    redirect_legacy_users_admin,
)

urlpatterns = [
    re_path(LEGACY_USERS_ADMIN_PATTERN, redirect_legacy_users_admin),
    path("admin/", admin.site.urls),
    path("", include("attendance.urls")),
    path("", include("registry.urls")),
    path("", include("users.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
