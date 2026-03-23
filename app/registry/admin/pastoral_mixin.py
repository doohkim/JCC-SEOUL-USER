"""교적(registry) Admin: 목사·전도사만 접근 (직급 코드 pastor / evangelist 또는 level ≥ 80)."""

from __future__ import annotations

from users.permissions import can_access_member_registry


class PastoralRegistryModelAdminMixin:
    """registry 모델 Admin — ``can_access_member_registry`` 가 아니면 메뉴·CRUD 불가."""

    def has_module_permission(self, request):
        """Django 6+: ``(request,)`` 만 받음 — ``app_label`` 은 ``self.opts`` 로 판별."""
        if not request.user.is_active or not request.user.is_authenticated:
            return False
        if not can_access_member_registry(request.user):
            return False
        return super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        if not can_access_member_registry(request.user):
            return False
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        if not can_access_member_registry(request.user):
            return False
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if not can_access_member_registry(request.user):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not can_access_member_registry(request.user):
            return False
        return super().has_delete_permission(request, obj)
