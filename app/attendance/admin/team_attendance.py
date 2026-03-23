"""팀 출석부 (팀+날짜 · 교시별 인천/서울/온라인/미선택 칩)."""

from django.contrib import admin, messages
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path

from attendance.choices import AttendanceChip
from attendance.models import TeamAttendanceSession, TeamMemberSlotAttendance
from registry.models import Member
from users.admin.audit import AuditLoggingModelAdminMixin


class JccModelAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("admin/css/jcc_fieldsets.css",)}


class TeamMemberSlotAttendanceInline(admin.TabularInline):
    model = TeamMemberSlotAttendance
    extra = 0
    autocomplete_fields = ["member"]
    fields = ["member", "slot_index", "picks"]


@admin.register(TeamAttendanceSession)
class TeamAttendanceSessionAdmin(AuditLoggingModelAdminMixin, JccModelAdmin):
    change_form_template = "admin/attendance/team_session_change_form.html"

    list_display = [
        "team",
        "session_date",
        "title",
        "period_count",
        "slot_row_count",
        "updated_at",
    ]
    list_filter = ["team__division", "session_date"]
    search_fields = ["title", "notes", "team__name", "team__code"]
    autocomplete_fields = ["team"]
    date_hierarchy = "session_date"
    inlines = [TeamMemberSlotAttendanceInline]
    fieldsets = (
        (
            "필수",
            {"classes": ("jcc-required",), "fields": ("team", "session_date")},
        ),
        (
            "교시(앱·보드)",
            {
                "classes": ("jcc-optional",),
                "fields": ("period_count", "period_labels", "title"),
                "description": "모바일 출석 UI의 1교시·2교시 행 수와 라벨입니다.",
            },
        ),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": ("notes", "created_by", "updated_by"),
            },
        ),
    )
    readonly_fields = ["created_by", "updated_by"]

    @admin.display(description="교시 행 수")
    def slot_row_count(self, obj):
        if hasattr(obj, "_slot_row_count"):
            return obj._slot_row_count
        return obj.slot_rows.count()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_slot_row_count=Count("slot_rows", distinct=True))

    def get_urls(self):
        opts = self.model._meta

        def slot_board(request, object_id):
            return self._slot_board_view(request, object_id)

        custom = [
            path(
                "<path:object_id>/slot-board/",
                self.admin_site.admin_view(slot_board),
                name=f"{opts.app_label}_{opts.model_name}_slot_board",
            ),
        ]
        return custom + super().get_urls()

    def _slot_board_view(self, request, object_id):
        try:
            pk = int(object_id)
        except (TypeError, ValueError) as e:
            raise Http404 from e
        session = get_object_or_404(
            TeamAttendanceSession.objects.select_related("team", "team__division"),
            pk=pk,
        )
        labels = session.effective_period_labels()
        n = len(labels)
        chips = list(AttendanceChip.choices)
        allowed = {c[0] for c in chips}

        from_team = session.roster_members()
        from_slots = Member.objects.filter(team_slot_attendances__session=session).distinct()
        members = (from_team | from_slots).distinct().order_by("name")

        if request.method == "POST":
            for mid in members.values_list("pk", flat=True):
                for si in range(1, n + 1):
                    key = f"pick_{mid}_{si}"
                    vals = [v for v in request.POST.getlist(key) if v in allowed]
                    if vals:
                        try:
                            row = TeamMemberSlotAttendance.objects.get(
                                session=session,
                                member_id=mid,
                                slot_index=si,
                            )
                        except TeamMemberSlotAttendance.DoesNotExist:
                            row = TeamMemberSlotAttendance(
                                session=session,
                                member_id=mid,
                                slot_index=si,
                                created_by=request.user,
                            )
                        row.picks = vals
                        row.updated_by = request.user
                        row.full_clean()
                        row.save()
                    else:
                        TeamMemberSlotAttendance.objects.filter(
                            session=session,
                            member_id=mid,
                            slot_index=si,
                        ).delete()
            messages.success(request, "교시별 출석을 저장했습니다.")
            return redirect("admin:attendance_teamattendancesession_slot_board", object_id=pk)

        grid = {}
        for row in TeamMemberSlotAttendance.objects.filter(session=session):
            grid[(row.member_id, row.slot_index)] = set(row.picks)

        member_rows = []
        for m in members:
            cells = []
            for si in range(1, n + 1):
                cells.append({"slot": si, "picked": grid.get((m.pk, si), set())})
            member_rows.append({"member": m, "cells": cells})

        context = {
            **self.admin_site.each_context(request),
            "title": f"교시별 출석 — {session}",
            "session": session,
            "labels": labels,
            "chips": chips,
            "member_rows": member_rows,
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request, None),
        }
        return render(request, "admin/attendance/team_session_slot_board.html", context)


@admin.register(TeamMemberSlotAttendance)
class TeamMemberSlotAttendanceAdmin(AuditLoggingModelAdminMixin, JccModelAdmin):
    list_display = ["session", "member", "slot_index", "picks", "updated_at"]
    list_filter = ["session__team__division", "session__session_date"]
    search_fields = ["member__name", "session__team__name"]
    autocomplete_fields = ["session", "member"]
    readonly_fields = ["created_by", "updated_by"]
    fieldsets = (
        ("필수", {"classes": ("jcc-required",), "fields": ("session", "member", "slot_index")}),
        (
            "선택",
            {
                "classes": ("jcc-optional",),
                "fields": ("picks", "created_by", "updated_by"),
            },
        ),
    )
