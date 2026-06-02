from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatEvent, RetreatSession


class RetreatSessionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RetreatSession
        fields = [
            "id",
            "name",
            "occurs_at",
            "sequence",
            "location",
            "status",
            "status_display",
            "closed_at",
            "closed_by",
            "created_at",
            "created_by",
            "created_by_name",
        ]
        read_only_fields = [
            "status_display",
            "closed_by",
            "created_at",
            "created_by",
            "created_by_name",
        ]
        extra_kwargs = {
            # closed_at은 status=CLOSED일 때만 의미가 있고, 비워두면 서버가 자동 채움.
            "closed_at": {"required": False, "allow_null": True},
            "status": {"required": False},
        }

    def get_created_by_name(self, obj) -> str:
        if obj.created_by_id and obj.created_by:
            return obj.created_by.get_username()
        return ""

    def validate(self, attrs):
        # ACTIVE 상태로 저장될 경우 closed_at은 절대 남기지 않는다.
        new_status = attrs.get(
            "status",
            getattr(self.instance, "status", RetreatSession.Status.ACTIVE),
        )
        if new_status == RetreatSession.Status.ACTIVE:
            attrs["closed_at"] = None
        return attrs


class RetreatEventSerializer(serializers.ModelSerializer):
    sessions = serializers.SerializerMethodField()

    class Meta:
        model = RetreatEvent
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "is_active",
            "sessions",
        ]

    def get_sessions(self, obj):
        request = self.context.get("request")
        if request is None:
            qs = obj.sessions.order_by("-created_at", "-id")
        else:
            from users.permissions import visible_retreat_sessions_for

            qs = visible_retreat_sessions_for(request.user, obj).order_by(
                "-created_at", "-id"
            )
        return RetreatSessionSerializer(qs, many=True).data
