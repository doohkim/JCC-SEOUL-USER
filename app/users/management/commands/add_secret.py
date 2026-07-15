from argparse import RawTextHelpFormatter
from copy import deepcopy

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management import BaseCommand

from config.settings._base import _secrets as secrets
from config.settings._base._crypto import key as crypto_key


def get_help_text() -> str:
    section_text = ""
    if hasattr(secrets, "ENCRYPTED_SECRETS"):
        for section, section_items in secrets.ENCRYPTED_SECRETS.items():
            section_text += " {section}: ".format(section=section)
            for key in section_items.keys():
                section_text += f"\n  {key}"
            section_text += "\n"

    return f"""
config.settings._base._secrets에 새 비밀값을 추가합니다.
python manage.py add_secret <section> <key> <value>를 사용합니다.\n
현재 저장되어 있는 비밀값은 아래와 같습니다. (각 Section과 Section에 속하는 항목들)
{section_text}
"""


CODE_START = """from cryptography.fernet import Fernet as __Fernet

from ._crypto import key as __key

__f = __Fernet(__key)


def decode_encrypted_secret(value):
    return __f.decrypt(value.encode("utf-8")).decode("utf-8")
"""

CODE_END = """all_secrets = locals()


def show_secrets():
    for key in [key for key in all_secrets if not key.startswith("__") and key != "ENCRYPTED_SECRETS" and key.isupper()]:
        value = all_secrets[key]
        print(f"{key}\\n {value}\\n")
"""


class Command(BaseCommand):
    help = get_help_text()

    def create_parser(self, *args, **kwargs):
        parser = super().create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument("section", type=str, help="")
        parser.add_argument("key", type=str)
        parser.add_argument("value", type=str)
        parser.add_argument("--print", action="store_true", help="추가 결과를 콘솔에 프린트")

    def handle(self, *args, **options):
        section = options["section"]
        key = options["key"]
        value = options["value"]

        # 주어진 값 encrypt
        f = Fernet(crypto_key)
        result = f.encrypt(value.encode("utf-8"))
        encrypted_value = result.decode("utf-8")

        # ENCRYPTED_SECRETS에 값 추가
        if hasattr(secrets, "ENCRYPTED_SECRETS"):
            new_secrets = deepcopy(secrets.ENCRYPTED_SECRETS)
        else:
            new_secrets = {}
        new_secrets.setdefault(section, {})
        new_secrets[section][key] = encrypted_value

        # secrets.py 새로 작성
        dict_text = "\n\nENCRYPTED_SECRETS = {\n"
        for secret_section, section_dict in new_secrets.items():
            section_text = f'    "{secret_section}": {{\n'
            for secret_key, secret_value in section_dict.items():
                section_text += f'        "{secret_key}": "{secret_value}",\n'
            section_text += "    },\n"
            dict_text += section_text
        dict_text += "}\n"

        attributes_text = "\n"
        for secret_section, section_dict in new_secrets.items():
            section_text = f"# {secret_section}\n"
            for secret_key, _secret_value in section_dict.items():
                section_text += (
                    f'{secret_key} = decode_encrypted_secret('
                    f'ENCRYPTED_SECRETS["{secret_section}"]["{secret_key}"])\n'
                )
            section_text += "\n"
            attributes_text += section_text
        attributes_text += "\n"

        secrets_text = CODE_START + dict_text + attributes_text + CODE_END
        if options["print"]:
            print(secrets_text)
        open(settings.BASE_DIR / "config/settings/_base/_secrets.py", "wt").write(secrets_text)
