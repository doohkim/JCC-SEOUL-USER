daemon = False
chdir = "/srv/app"
bind = "0.0.0.0:8000"
workers = 1
threads = 1
timeout = 60
capture_output = True
enable_stdio_inheritance = True
raw_env = [
    "DJANGO_SETTINGS_MODULE=config.settings.production",
]
