from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.views.generic import TemplateView

from config.urls._base import urlpatterns as base_urlpatterns
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.admin_legacy_redirect import (
    LEGACY_USERS_ADMIN_PATTERN,
    redirect_legacy_users_admin,
)
from config.views import api_root_redirect

api_urlpatterns = [
    path(
        "",
        api_root_redirect,
        name="root_login_redirect",
    ),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    re_path(LEGACY_USERS_ADMIN_PATTERN, redirect_legacy_users_admin),
    re_path(LEGACY_USERS_ADMIN_PATTERN, redirect_legacy_users_admin),
    path("docs/", TemplateView.as_view(template_name="docs/index.html"), name="docs_index"),
    path("auth/", include("social_django.urls", namespace="social")),
    path("", include("attendance.urls")),
    path("", include("registry.urls")),
    path("", include("users.urls")),
    path("", include("counseling.urls")),

]
urlpatterns = base_urlpatterns + api_urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
