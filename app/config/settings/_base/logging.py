LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "users.admin": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "users.import": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "users.org": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "users.services.kakao_auth": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
