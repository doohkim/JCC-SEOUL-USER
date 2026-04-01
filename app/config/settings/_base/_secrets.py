from cryptography.fernet import Fernet as __Fernet

from ._crypto import key as __key

__f = __Fernet(__key)


def decode_encrypted_secret(value):
    return __f.decrypt(value.encode("utf-8")).decode("utf-8")


ENCRYPTED_SECRETS = {
    "DJANGO": {
        "DJANGO_SECRET_KEY": "gAAAAABni2tYOgqDE2B52XW4-Z5rQLnL8Pnn9HguvTXz9w_iR6Z4zqETowE7RST5RQCYcoEKyF8QawJ9uscNwrbaCwuwLrushq-Hz6A1sHgzHgCPIZKKMD2PzbHuU4_izXCo6l0Cyhnro8o8KXw7HTTvTw7mgx7j-0iO8XF6w8Jia-6H6PmVfi0=",
    },
    "DATABASE": {
        "DB_NAME": "gAAAAABni2yf6gM2Tn8yG8PjUHjU68pYYHKWh1G-dLo56OrZtbNlQ1Ag_KsXtRTC8cdx8HY5xzSycTj8fWJBXmxiO3rl9shaMw==",
        "DB_USERNAME": "gAAAAABni2xvnkIqcbEqNugw7YVBqpoo4V1oL1hA2osq-nmsC3QxrT1ohhpreg7hAxsFOpRJiA3wztTBs4XLQE4VUES8IQpOVA==",
        "DB_PASSWORD_LOCAL": "gAAAAABni2w4EZcTYLPbCkwaNVxZDbPYGG8B_-IUdx8SIimgbEGhZM382zNFDTUuMMiAPpDDUPOBCOJXnwExA80dYi1VN-1uLw==",
        "DB_PORT_LOCAL": "gAAAAABni23ZwCnfV8dv33j16QXK26UejwnXM6ZWLlj0ePvkiPCYHv-vBMbGGE1oEKVQjAERarCE5es-y4t9PJHzHkK5bi8K_g==",
        "DB_HOST_PRODUCTION": "gAAAAABni21sCbT_I6IvsTsfTTZQRyVHXiL4otnxB_Ge_XSyGnq0VAWlt84592rYjR7s9krPIDLYcl-Z_lOFlSVWOvGTTMaHew==",
        "DB_NAME_PRODUCTION": "gAAAAABni2zcm0sDE1YoRSHL8YeVOinpWrhEXaCNHTW7Rm_r9IpPnVSeuhZZGdCfbHBXnfLWq_q1ceKOeiP-vkN5wZwLcNg_SA==",
        "DB_USERNAME_PRODUCTION": "gAAAAABni2zzw5QS-Nem0z8MyoTir6uqNKs-TAx1-KZjCamb-ZtU8Hh7iTgx7WVoSr9OHy94t02IPFftOTMhQ1H5x6m5fMQgpg==",
        "DB_PASSWORD_PRODUCTION": "gAAAAABni20EKvRDRPA7r0I46ChODsUVZCgrcN-5VQKwT-uwoWombFq1lm4gSsTCx1VSbn5rhaoYIfV5WHGPUN4P8Fnp7Xo6EA==",
        "DB_PORT_PRODUCTION": "gAAAAABni22HmIHpJkLjgqzhlOGHaUjAhXl6Ton5sWyWXM8WSEmY_49Xi-Sbdzu2Rl7I19l39-S99l1M7WRzRW-HwUvicp4IqA==",
        "RDS_HOST_PRODUCTION": "gAAAAABn0TgpHQPB9RbgXaXhT8zqj5sDqARGJyZZQIiCsC6rf4gB2taiWzdGL5kWFRUOefzeZFveiJn1eyEfNjvQrNwphYQVFtjzuPZ2-sQmRpU9DxP_y1iPYVNBfYq3ys8U1u4l_ZDfBIMpkKtYPFIlZeur-H9MzA==",
        "RDS_PORT_PRODUCTION": "gAAAAABnz310IUs2JxDFYgRZL49uqrO1TRK9vbryyR3_LMzbrl2F2R-0zlmB36Ukk29Hsha3vXkLQpWNbVVoRq7Hdcpgh0lQuw==",
        "RDS_PASSWORD_PRODUCTION": "gAAAAABnz350T-KtGQcWnRiHsvTYYO9sJ4diK040cLepuRIyGtHncE2BFrGfJVOg6MFvGkaMRqcM6TM_btPzU9poNVBVo2SoFQ==",
    },
    "SERVICE": {
        "RABBITMQ_PASSWORD": "gAAAAABnmzRx0om1p6C1X_gh5W4edMMLkgijeVmBqzgrwYQBxvbCLgPzMZZtbC6pzNHVgTpVCSheNmAc-JtCBB8dljibCHYecA==",
    },
}

# DJANGO
DJANGO_SECRET_KEY = decode_encrypted_secret(ENCRYPTED_SECRETS["DJANGO"]["DJANGO_SECRET_KEY"])

# DATABASE
DB_NAME = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["DB_NAME"])
DB_USERNAME = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["DB_USERNAME"])
DB_PASSWORD_LOCAL = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["DB_PASSWORD_LOCAL"])
DB_PORT_LOCAL = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["DB_PORT_LOCAL"])
DB_HOST_PRODUCTION = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["DB_HOST_PRODUCTION"])
DB_NAME_PRODUCTION = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["DB_NAME_PRODUCTION"])
DB_USERNAME_PRODUCTION = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["DB_USERNAME_PRODUCTION"])
DB_PASSWORD_PRODUCTION = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["DB_PASSWORD_PRODUCTION"])
DB_PORT_PRODUCTION = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["DB_PORT_PRODUCTION"])
RDS_HOST_PRODUCTION = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["RDS_HOST_PRODUCTION"])
RDS_PORT_PRODUCTION = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["RDS_PORT_PRODUCTION"])
RDS_PASSWORD_PRODUCTION = decode_encrypted_secret(ENCRYPTED_SECRETS["DATABASE"]["RDS_PASSWORD_PRODUCTION"])

# SERVICE
RABBITMQ_PASSWORD = decode_encrypted_secret(ENCRYPTED_SECRETS["SERVICE"]["RABBITMQ_PASSWORD"])



all_secrets = locals()


def show_secrets():
    for key in [key for key in all_secrets if not key.startswith("__") and key != "ENCRYPTED_SECRETS" and key.isupper()]:
        value = all_secrets[key]
        print(f"{key}\n {value}\n")
