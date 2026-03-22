from django.apps import AppConfig


class RegistryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "registry"
    label = "registry"
    verbose_name = "교적부"

    def ready(self):
        from django.db.models.signals import post_save

        from registry.models import Member, MemberProfile

        def ensure_member_profile(sender, instance: Member, created, **kwargs):
            if created:
                MemberProfile.objects.get_or_create(member=instance)

        post_save.connect(ensure_member_profile, sender=Member, weak=False)
