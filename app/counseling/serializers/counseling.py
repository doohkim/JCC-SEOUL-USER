from __future__ import annotations

from rest_framework import serializers

from counseling.models import (
    PastorDayOverride,
    PastorScheduleSettings,
    CounselingRequest,
    CounselingSlot,
)
from users.services.user_display import user_display_name


class PastorScheduleSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PastorScheduleSettings
        fields = (
            "slot_duration_minutes",
            "default_start_hour",
            "default_end_hour",
            "weekday_hours_json",
            "updated_at",
        )
        read_only_fields = ("updated_at",)


class PastorDayOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = PastorDayOverride
        fields = ("id", "date", "is_closed", "custom_slots_json", "updated_at")
        read_only_fields = ("id", "updated_at")


class CounselingSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CounselingSlot
        fields = (
            "id",
            "pastor_id",
            "date",
            "start_time",
            "end_time",
            "state",
        )


class CounselingRequestSerializer(serializers.ModelSerializer):
    slot = CounselingSlotSerializer(read_only=True)
    applicant_label = serializers.SerializerMethodField()
    pastor_label = serializers.SerializerMethodField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and request.user.pk != instance.pastor_id:
            data["pastor_notes_json"] = {}
        return data

    class Meta:
        model = CounselingRequest
        fields = (
            "public_id",
            "applicant_id",
            "pastor_id",
            "applicant_label",
            "pastor_label",
            "status",
            "applicant_message",
            "pastor_notes_json",
            "slot",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "public_id",
            "applicant_id",
            "pastor_id",
            "status",
            "applicant_message",
            "pastor_notes_json",
            "slot",
            "created_at",
            "updated_at",
        )

    def get_applicant_label(self, obj):
        return user_display_name(obj.applicant)

    def get_pastor_label(self, obj):
        return user_display_name(obj.pastor)


class CounselingRequestCreateSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField(min_value=1)
    applicant_message = serializers.CharField(allow_blank=True, default="")


class CounselingRequestUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CounselingRequest
        fields = ("applicant_message", "pastor_notes_json")

    def validate(self, attrs):
        req = self.instance
        user = self.context["request"].user
        if not req:
            return attrs
        if "applicant_message" in attrs:
            if req.applicant_id != user.pk:
                raise serializers.ValidationError(
                    {"applicant_message": "수정할 수 없습니다."}
                )
            if req.status != CounselingRequest.Status.PENDING:
                raise serializers.ValidationError(
                    {"applicant_message": "대기 중만 수정할 수 있습니다."}
                )
        if "pastor_notes_json" in attrs:
            if req.pastor_id != user.pk:
                raise serializers.ValidationError(
                    {"pastor_notes_json": "목회자만 수정할 수 있습니다."}
                )
        return attrs
