import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission


class IsResponsable(BasePermission):
    message = "Accès réservé au responsable."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_responsable
        )


class IsLivreur(BasePermission):
    message = "Accès réservé aux livreurs."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and not request.user.is_responsable
            and hasattr(request.user, "profil_livreur")
        )


class HasGPSAPIKey(BasePermission):
    message = "Clé API GPS absente ou invalide."

    def has_permission(self, request, view):
        api_key = request.headers.get("X-API-Key", "")
        expected_key = settings.GPS_API_KEY
        return bool(
            api_key
            and expected_key
            and secrets.compare_digest(api_key.strip(), expected_key.strip())
        )
