"""멤버 가족·심방(연락) 관련 TextChoices."""

from django.db import models


class RelationshipKind(models.TextChoices):
    """가족 구성원 관계 (``MemberFamilyMember``)."""

    FATHER = "father", "부"
    MOTHER = "mother", "모"
    SPOUSE = "spouse", "배우자"
    ELDER_BROTHER = "elder_brother", "형/오빠"
    YOUNGER_BROTHER = "younger_brother", "남동생"
    ELDER_SISTER = "elder_sister", "언니/누나"
    YOUNGER_SISTER = "younger_sister", "여동생"
    SON = "son", "아들"
    DAUGHTER = "daughter", "딸"
    OTHER = "other", "기타"


class VisitContactMethod(models.TextChoices):
    """심방·연락 방식 (``MemberVisitLog``)."""

    PHONE = "phone", "전화"
    VISIT = "visit", "방문"
    OTHER = "other", "기타"


ShepherdingContactMethod = VisitContactMethod
