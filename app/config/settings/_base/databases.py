from . import _secrets as secrets

DB_NAME = secrets.DB_NAME
DB_USERNAME = secrets.DB_USERNAME
DB_PASSWORD_LOCAL = secrets.DB_PASSWORD_LOCAL

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "localhost",
        "PORT": "55432",
        "NAME": DB_NAME,
        "USER": DB_USERNAME,
        "PASSWORD": DB_PASSWORD_LOCAL,
    }
}
