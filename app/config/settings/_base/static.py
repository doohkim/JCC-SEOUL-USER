from ._path import ROOT_DIR, STATIC_DIR

# Static
STATIC_URL = "/static/"  # 정적 파일을 서비스할 URL 경로

STATIC_ROOT = ROOT_DIR / ".static"  # collectstatic 명령어를 실행할 때 모든 정적 파일이 모이는 디렉터리 경로
STATICFILES_DIRS = [
    STATIC_DIR,
]
# Media
MEDIA_URL = "/media/"  # 미디어 파일을 서비스할 URL 경로
MEDIA_ROOT = ROOT_DIR / ".media"
