"""
Admin 모듈. models 패키지와 같이 역할별 파일로 분리.

- accounts: User, RoleLevel
- organization: Division, Team, Club, … (조직 마스터)

교적(Member)·출석은 각각 ``registry``·``attendance`` 앱 admin에서 등록합니다.
"""

from . import accounts  # noqa: F401
from . import organization  # noqa: F401
