"""
멤버 부가 정보: 가족 행, 심방·통화 기록.

목양 대상도 동일하게 ``Member`` 한 모델로 관리합니다.
"""

from django.db import models

from ..choices import RelationshipKind, VisitContactMethod
from .member import Member
from .organization import Division
from .user import User


class MemberFamilyMember(models.Model):
    """멤버 카드의 가족 표 한 행."""

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="family_members",
        verbose_name="멤버",
    )
    name = models.CharField("이름", max_length=50)
    relationship = models.CharField(
        "관계",
        max_length=30,
        choices=RelationshipKind.choices,
        default=RelationshipKind.OTHER,
    )
    relationship_note = models.CharField(
        "관계(직접입력)",
        max_length=50,
        blank=True,
        default="",
        help_text="기타 선택 시 또는 세부 표기",
    )
    affiliation_text = models.CharField(
        "소속",
        max_length=100,
        blank=True,
        default="",
        help_text="예: 광명교구, 청년부, 불신",
    )
    division = models.ForeignKey(
        Division,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="member_family_affiliations",
        verbose_name="소속 부서(선택)",
        help_text="카드 표기와 맞출 때만 연결",
    )
    church_position = models.CharField("직분", max_length=100, blank=True, default="")
    remarks = models.TextField("비고", blank=True, default="")
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "멤버 가족"
        verbose_name_plural = "멤버 가족"
        ordering = ["member", "sort_order", "id"]

    def __str__(self):
        return f"{self.member.name}의 가족 · {self.name}"


class MemberVisitLog(models.Model):
    """심방·통화 등 목양 기록 (멤버 단위)."""

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="visit_logs",
        verbose_name="멤버",
    )
    visit_date = models.DateField(
        "심방일(기준일)",
        help_text="매주 통화면 해당 주 대표일(예: 통화한 날)",
    )
    contact_method = models.CharField(
        "방식",
        max_length=20,
        choices=VisitContactMethod.choices,
        default=VisitContactMethod.PHONE,
    )
    content = models.TextField(
        "내용",
        help_text="상황, 대화 요약 등",
    )
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_member_visits",
        verbose_name="기록자",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "멤버 심방 기록"
        verbose_name_plural = "멤버 심방 기록"
        ordering = ["-visit_date", "-created_at"]
        indexes = [
            models.Index(fields=["member", "-visit_date"]),
        ]

    def __str__(self):
        return f"{self.member.name} · {self.visit_date}"
