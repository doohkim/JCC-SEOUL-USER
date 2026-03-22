"""관리자 저장 시 수정자 기록 + 필드 단위 로깅."""

from __future__ import annotations

import logging

logger = logging.getLogger("users.admin")


def _audit_assign(request, instance, *, created: bool) -> None:
    if not hasattr(instance, "updated_by_id"):
        return
    instance.updated_by = request.user
    if created and hasattr(instance, "created_by_id"):
        instance.created_by = request.user


def _log_form_changes(request, obj, form, change: bool, *, model_label: str) -> None:
    if not change or not hasattr(form, "changed_data"):
        return
    for name in form.changed_data:
        try:
            old = form.initial.get(name)
        except Exception:  # pragma: no cover
            old = "(조회 실패)"
        try:
            new = form.cleaned_data.get(name, getattr(obj, name, None))
        except Exception:  # pragma: no cover
            new = "(조회 실패)"
        logger.info(
            "admin_change model=%s pk=%s field=%s editor=%s old=%r new=%r",
            model_label,
            getattr(obj, "pk", None),
            name,
            getattr(request.user, "username", None) or request.user,
            old,
            new,
        )


class AuditLoggingModelAdminMixin:
    """
    모델에 ``created_by`` / ``updated_by`` 가 있으면 채우고,
    수정 시 ``changed_data`` 를 ``users.admin`` 로거로 남깁니다.
    """

    def save_model(self, request, obj, form, change):
        created = not change
        _audit_assign(request, obj, created=created)
        super().save_model(request, obj, form, change)
        _log_form_changes(
            request,
            obj,
            form,
            change,
            model_label=obj.__class__.__name__,
        )

    def save_formset(self, request, form, formset, change):
        for f in formset.forms:
            if not f.is_bound:
                continue
            if not f.cleaned_data:
                continue
            if f.cleaned_data.get("DELETE"):
                continue
            inst = f.instance
            if not f.has_changed() and inst.pk:
                continue
            created = not bool(inst.pk)
            _audit_assign(request, inst, created=created)
        super().save_formset(request, form, formset, change)
        for f in formset.forms:
            if not f.is_bound or not f.cleaned_data or f.cleaned_data.get("DELETE"):
                continue
            if not f.has_changed():
                continue
            inst = f.instance
            if not inst.pk:
                continue
            for name in f.changed_data:
                old = f.initial.get(name, "(없음)")
                new = f.cleaned_data.get(name)
                logger.info(
                    "admin_inline_change model=%s pk=%s field=%s editor=%s old=%r new=%r",
                    inst.__class__.__name__,
                    inst.pk,
                    name,
                    getattr(request.user, "username", None) or request.user,
                    old,
                    new,
                )
