from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Affectation,
    Alert,
    Livreur,
    Mission,
    Moto,
    PositionGPS,
    PreuveLivraison,
    User,
)


@admin.register(User)
class MotoTrackUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("MotoTrack", {"fields": ("role", "telephone")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("MotoTrack", {"fields": ("role", "telephone")}),
    )


admin.site.register(Moto)
admin.site.register(Livreur)
admin.site.register(Affectation)
admin.site.register(Mission)
admin.site.register(PositionGPS)
admin.site.register(PreuveLivraison)
admin.site.register(Alert)
