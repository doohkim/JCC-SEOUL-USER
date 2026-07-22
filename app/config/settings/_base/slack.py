import sys

from . import _secrets as secrets

SLACK_TOKEN = secrets.SLACK_TOKEN
# manage.py test 실행 시 실제 Slack API 호출을 막는다.
SLACK_NOTIFICATIONS_ENABLED = not (len(sys.argv) >= 2 and sys.argv[1] == "test")
