from . import _secrets as secrets

AWS_STORAGE_BUCKET_NAME = secrets.S3_STORAGE_BUCKET_NAME
AWS_S3_REGION_NAME = "ap-northeast-2"
AWS_ACCESS_KEY_ID = secrets.S3_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = secrets.S3_SECRET_ACCESS_KEY
AWS_S3_CUSTOM_DOMAIN = secrets.S3_CUSTOM_DOMAIN


def build_storage_settings(
    *,
    bucket_name,
    region_name="ap-northeast-2",
    location="",
    custom_domain=None,
    access_key="",
    secret_key="",
):
    bucket_name = (bucket_name or "").strip()
    region_name = (region_name or "ap-northeast-2").strip()
    location = (location or "").strip("/")
    custom_domain = (custom_domain or "").strip() or None
    access_key = (access_key or "").strip()
    secret_key = (secret_key or "").strip()

    staticfiles_storage = {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    }
    if not bucket_name:
        storages = {
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": staticfiles_storage,
        }
        return storages, None

    s3_options = {
        "bucket_name": bucket_name,
        "region_name": region_name,
        "default_acl": None,
        "querystring_auth": False,
        "file_overwrite": False,
        "location": location,
    }
    if access_key:
        s3_options["access_key"] = access_key
    if secret_key:
        s3_options["secret_key"] = secret_key
    if custom_domain:
        s3_options["custom_domain"] = custom_domain

    storages = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": s3_options,
        },
        "staticfiles": staticfiles_storage,
    }
    media_domain = custom_domain or f"{bucket_name}.s3.{region_name}.amazonaws.com"
    media_url = f"https://{media_domain}/"
    if location:
        media_url = f"{media_url}{location}/"
    return storages, media_url
