"""공지사항 DRF serializers."""

from rest_framework import serializers

from notices.models import NoticeCategory


class NoticeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = NoticeCategory
        fields = ("id", "name", "slug", "color")
