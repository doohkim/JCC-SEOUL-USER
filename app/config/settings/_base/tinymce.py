"""TinyMCE 리치 텍스트 에디터 설정."""

TINYMCE_DEFAULT_CONFIG = {
    "height": 420,
    "menubar": False,
    "plugins": "lists link image table fullscreen autolink",
    "toolbar": (
        "bold italic underline | alignleft aligncenter alignright "
        "| bullist numlist | link image table | fullscreen"
    ),
    "branding": False,
    "statusbar": True,
    "elementpath": False,
    "language": "ko_KR",
    "convert_urls": False,
    # 본문 인라인 이미지 업로드 (notice_form.html 에서 window.jccNoticeImageUpload 정의)
    "automatic_uploads": True,
    "images_file_types": "jpeg,jpg,png,gif,webp",
    "file_picker_types": "image",
    "images_upload_handler": "jccNoticeImageUpload",
}
