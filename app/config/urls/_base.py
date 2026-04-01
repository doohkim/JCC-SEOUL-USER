from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

# from utils.logging import getLogger

# logger = getLogger(__name__)

urlpatterns = []
if settings.DEBUG:
    try:
        import debug_toolbar

        debug_urls = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + [
            path("__debug__/", include(debug_toolbar.urls)),
        ]
        urlpatterns += debug_urls
    except ModuleNotFoundError as e:
        pass
        # logger.warning("DEBUG가 True이나 debug_toolbar가 없습니다")
