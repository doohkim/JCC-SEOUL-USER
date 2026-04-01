import os

IS_DOCKER = bool(os.environ.get("IS_DOCKER"))
REDIS_HOST = "redis" if IS_DOCKER else "127.0.0.1"

__all__ = ("CACHES",)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:6379/1",
    }
}
