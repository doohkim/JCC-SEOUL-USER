from __future__ import annotations

from rest_framework import serializers

from retreat.models import RetreatAttendee
from retreat.services.check_in_stamps import is_expected_timestamps_locked
from users.validators import normalize_korea_mobile_phone


class RetreatAttendeeSerializer(serializers.ModelSerializer):
    gender_display = serializers.CharField(source="get_gender_display", read_only=True)
    check_in_status_display = serializers.CharField(
        source="get_check_in_status_display", read_only=True
    )
    participation_status_display = serializers.CharField(
        source="get_participation_status_display", read_only=True
    )
    member_role_display = serializers.CharField(
        source="get_member_role_display", read_only=True
    )
    user_label = serializers.SerializerMethodField()
    lodging_room_label = serializers.SerializerMethodField()
    expected_timestamps_locked = serializers.SerializerMethodField()

    class Meta:
        model = RetreatAttendee
        fields = [
            "id",
            "group",
            "user",
            "user_label",
            "member_role",
            "member_role_display",
            "name",
            "phone",
            "gender",
            "gender_display",
            "memo",
            "participation_status",
            "participation_status_display",
            "check_in_status",
            "check_in_status_display",
            "expected_check_in_at",
            "expected_check_out_at",
            "checked_in_at",
            "checked_out_at",
            "source_member",
            "lodging_room",
            "lodging_room_label",
            "expected_timestamps_locked",
            "sort_order",
        ]
        read_only_fields = [
            "id",
            "gender_display",
            "check_in_status_display",
            "member_role_display",
            "user_label",
            "participation_status_display",
            "lodging_room_label",
            "expected_timestamps_locked",
        ]

    def get_user_label(self, attendee: RetreatAttendee) -> str:
        user = attendee.user
        if not user:
            return ""
        from users.services.user_display import user_display_name

        profile = getattr(user, "profile", None)
        real = (getattr(profile, "real_name", "") or "").strip()
        return real or user_display_name(user) or user.username

    def validate_name(self, value: str) -> str:
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("이름은 비워둘 수 없습니다.")
        return v

    def validate_phone(self, value: str) -> str:
        v = (value or "").strip()
        if not v:
            return ""
        normalized = normalize_korea_mobile_phone(v)
        if normalized is None:
            raise serializers.ValidationError(
                "휴대전화 형식이 아닙니다. 예: 010-1234-5678"
            )
        return normalized

    def get_expected_timestamps_locked(self, attendee: RetreatAttendee) -> bool:
        return is_expected_timestamps_locked(attendee)

    def validate(self, attrs):
        if self.instance and is_expected_timestamps_locked(self.instance):
            for key in ("expected_check_in_at", "expected_check_out_at"):
                if key in attrs:
                    raise serializers.ValidationError(
                        {
                            key: "자동 퇴실 처리된 조원의 입·퇴실 시각은 수정할 수 없습니다."
                        }
                    )
        # 부분 수정(PATCH)에서 한쪽만 들어와도 인스턴스 값과 합쳐 비교한다.
        sentinel = object()
        in_at = attrs.get("expected_check_in_at", sentinel)
        if in_at is sentinel:
            in_at = getattr(self.instance, "expected_check_in_at", None)
        out_at = attrs.get("expected_check_out_at", sentinel)
        if out_at is sentinel:
            out_at = getattr(self.instance, "expected_check_out_at", None)
        if in_at and out_at and out_at <= in_at:
            raise serializers.ValidationError(
                {"expected_check_out_at": "퇴실 시각은 입실 시각보다 뒤여야 합니다."}
            )
        participation = attrs.get("participation_status")
        if participation is None and self.instance:
            participation = self.instance.participation_status
        if (
            participation == RetreatAttendee.ParticipationStatus.ABSENT
            and "lodging_room" in attrs
            and attrs.get("lodging_room")
        ):
            raise serializers.ValidationError(
                {"lodging_room": "불참 조원에게는 숙소를 배정할 수 없습니다."}
            )
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        phone = data.get("phone")
        if phone:
            normalized = normalize_korea_mobile_phone(phone)
            if normalized:
                data["phone"] = normalized
        return data

    def get_lodging_room_label(self, attendee: RetreatAttendee) -> str:
        room = attendee.lodging_room
        if not room:
            return ""
        lodging = getattr(room, "lodging", None)
        lname = getattr(lodging, "name", "") or ""
        return (f"{lname} {room.number}" if lname else room.number).strip()
