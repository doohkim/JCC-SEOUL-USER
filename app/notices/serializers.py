"""공지사항 DRF serializers."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from notices.models import Notice, NoticeCategory
from users.services.user_display import user_display_name

_NOTICE_NEW_DAYS = 7


class NoticeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = NoticeCategory
        fields = ("id", "name", "slug", "color")


class NoticeListSerializer(serializers.ModelSerializer):
    category = NoticeCategorySerializer(read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()
    is_new = serializers.SerializerMethodField()
    target_label = serializers.CharField(read_only=True)

    class Meta:
        model = Notice
        fields = (
            "id",
            "title",
            "is_pinned",
            "thumbnail_url",
            "created_at",
            "view_count",
            "category",
            "is_new",
            "author_name",
            "target_label",
        )

    def get_thumbnail_url(self, obj: Notice) -> str | None:
        if not obj.thumbnail:
            return None
        request = self.context.get("request")
        url = obj.thumbnail.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_author_name(self, obj: Notice) -> str:
        if not obj.created_by_id:
            return ""
        return user_display_name(obj.created_by)

    def get_is_new(self, obj: Notice) -> bool:
        if not obj.created_at:
            return False
        return obj.created_at >= timezone.now() - timedelta(days=_NOTICE_NEW_DAYS)


class NoticeDetailSerializer(NoticeListSerializer):
    body = serializers.CharField(read_only=True)
    tags = serializers.SerializerMethodField()

    class Meta(NoticeListSerializer.Meta):
        fields = NoticeListSerializer.Meta.fields + ("body", "tags", "updated_at")

    def get_tags(self, obj: Notice) -> list[str]:
        return obj.tag_list
