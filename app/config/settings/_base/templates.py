from ._path import TEMPLATES_DIR, VIEWS_TEMPLATES_DIR, LIBRARY_TEMPLATES_DIR

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            TEMPLATES_DIR,
            LIBRARY_TEMPLATES_DIR,
            VIEWS_TEMPLATES_DIR,
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
            ],
            "libraries": {
                "permission_tags": "users.templatetags.permission_tags",
            },
        },
    },
]
