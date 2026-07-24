from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from retreat.apis._common import profile_locked_patch_keys_for
from retreat.models import RetreatAttendee
from retreat.services.account_retired import (
    ACCOUNT_RETIRED_DISPLAY,
    is_retired_account_row,
)
from retreat.services.check_in_stamps import (
    is_attendee_profile_locked,
    is_expected_timestamps_locked,
)
from retreat.services.lodging_stay import lodging_stay_display
from retreat.services.group_sync import apply_attendee_profile_defaults
from users.validators import normalize_korea_mobile_phone

User = get_user_model()


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
    lodging_stay_status = serializers.CharField(read_only=True)
    lodging_stay_display = serializers.SerializerMethodField()
    expected_timestamps_locked = serializers.SerializerMethodField()
    profile_locked = serializers.SerializerMethodField()
    account_retired = serializers.SerializerMethodField()
    account_retired_display = serializers.SerializerMethodField()

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
            "arrival_travel_is_custom",
            "departure_travel_is_custom",
            "checked_in_at",
            "checked_out_at",
            "source_member",
            "lodging_room",
            "lodging_room_label",
            "lodging_stay_status",
            "lodging_stay_display",
            "expected_timestamps_locked",
            "profile_locked",
            "account_retired",
            "account_retired_display",
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
            "lodging_stay_status",
            "lodging_stay_display",
            "expected_timestamps_locked",
            "profile_locked",
            "account_retired",
            "account_retired_display",
        ]

    def get_user_label(self, attendee: RetreatAttendee) -> str:
        user = attendee.user
        if not user:
            return ""
        from users.services.user_display import user_account_link_label

        return user_account_link_label(user)

    def to_internal_value(self, data):
        mutable = dict(data)
        user_ref = mutable.get("user")
        if user_ref:
            user = (
                user_ref
                if hasattr(user_ref, "pk")
                else User.objects.select_related("profile").filter(pk=user_ref).first()
            )
            if user:
                overwrite = self.instance is None
                if self.instance is not None and "user" in mutable:
                    overwrite = user.pk != (self.instance.user_id or None)
                mutable = apply_attendee_profile_defaults(
                    mutable,
                    user,
                    instance=self.instance,
                    overwrite=overwrite,
                )
        return super().to_internal_value(mutable)

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

    def get_profile_locked(self, attendee: RetreatAttendee) -> bool:
        return is_attendee_profile_locked(attendee)

    def get_account_retired(self, attendee: RetreatAttendee) -> bool:
        return is_retired_account_row(attendee)

    def get_account_retired_display(self, attendee: RetreatAttendee) -> str:
        return ACCOUNT_RETIRED_DISPLAY if is_retired_account_row(attendee) else ""

    def validate(self, attrs):
        if "user" in (self.initial_data or {}):
            linked_user = attrs.get("user")
            if linked_user is not None:
                overwrite = self.instance is None or linked_user.pk != (
                    self.instance.user_id or None
                )
                attrs = apply_attendee_profile_defaults(
                    attrs,
                    linked_user,
                    instance=self.instance,
                    overwrite=overwrite,
                )
        elif self.instance and self.instance.user_id:
            attrs = apply_attendee_profile_defaults(
                attrs,
                self.instance.user,
                instance=self.instance,
                overwrite=False,
            )
        if self.instance and is_attendee_profile_locked(self.instance):
            user = self.context.get("user")
            group = self.context.get("group")
            blocked = set(attrs.keys()) & profile_locked_patch_keys_for(
                user, group, self.instance
            )
            if blocked:
                msg = "퇴실 상태 조원의 정보는 수정할 수 없습니다."
                raise serializers.ValidationError({key: msg for key in blocked})
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
        # 시각을 비우면 해당 방향 자차 플래그도 null (명시 전송 없을 때만).
        if "expected_check_in_at" in attrs and not attrs.get("expected_check_in_at"):
            if "arrival_travel_is_custom" not in attrs:
                attrs["arrival_travel_is_custom"] = None
        if "expected_check_out_at" in attrs and not attrs.get("expected_check_out_at"):
            if "departure_travel_is_custom" not in attrs:
                attrs["departure_travel_is_custom"] = None
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

    def get_lodging_stay_display(self, attendee: RetreatAttendee) -> str:
        return lodging_stay_display(attendee)
