"""출석 API 공통 (페이지네이션·부서 접근)."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination

from users.models import Division
from users.permissions import visible_divisions_for


class StandardPagination(PageNumberPagination):
    page_size = 40
    page_size_query_param = "page_size"
    max_page_size = 200


def division_for_attendance_request(request, *, code_param: str | None = None) -> Division:
    code = code_param if code_param is not None else (request.query_params.get("division_code") or "youth")
    division = get_object_or_404(Division, code=code)
    if not visible_divisions_for(request.user).filter(pk=division.pk).exists():
        raise PermissionDenied("소속하지 않은 부서의 출석 데이터입니다.")
    return division
