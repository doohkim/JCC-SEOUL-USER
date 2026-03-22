"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
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
    # 구 Admin 경로(users 앱에 있던 교적·출석 모델) → attendance / registry
    re_path(LEGACY_USERS_ADMIN_PATTERN, redirect_legacy_users_admin),
    path("admin/", admin.site.urls),
    path("attendance/", include("attendance.urls")),
    path("api/v1/", include("users.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
