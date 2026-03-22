"""하위 호환 re-export. 새 코드는 ``user_org`` / ``member_org`` 사용 권장."""

from registry.services.member_org import (
    change_team_within_division as change_member_team_within_division,
    transfer_to_division as transfer_member_to_division,
)
from users.services.user_org import (
    change_team_within_division as change_user_team_within_division,
    transfer_to_division as transfer_user_to_division,
)

# API(교적) 하위 호환 이름
change_team_within_division = change_member_team_within_division
transfer_to_division = transfer_member_to_division

__all__ = [
    "change_team_within_division",
    "transfer_to_division",
    "change_member_team_within_division",
    "transfer_member_to_division",
    "change_user_team_within_division",
    "transfer_user_to_division",
]
