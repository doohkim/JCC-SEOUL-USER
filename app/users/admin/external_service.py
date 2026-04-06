"""연동 API 클라이언트(서비스 키) Admin."""

from django.contrib import admin, messages

from users.models import ExternalServiceClient
from users.models.external_service import generate_integration_key_pair


@admin.register(ExternalServiceClient)
class ExternalServiceClientAdmin(admin.ModelAdmin):
    list_display = ["name", "label", "key_prefix", "is_active", "last_used_at", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "label"]
    readonly_fields = ["key_prefix", "key_hash", "created_at", "updated_at", "last_used_at"]
    fieldsets = (
        (None, {"fields": ("name", "label", "is_active", "notes")}),
        ("키 해시", {"fields": ("key_prefix", "key_hash"), "description": "신규 저장 시 평문 키가 상단 메시지로 한 번 표시됩니다."}),
        ("감사", {"fields": ("last_used_at", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.pk:
            raw, prefix, khash = generate_integration_key_pair()
            obj.key_prefix = prefix
            obj.key_hash = khash
            super().save_model(request, obj, form, change)
            messages.warning(
                request,
                f"연동 API 키(다시 표시되지 않습니다): {raw}",
            )
            return
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and obj.pk:
            return ro + ["name"]
        return ro
