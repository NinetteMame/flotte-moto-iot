from django.conf import settings

from .services import alertes_pour_utilisateur, verifier_alertes_gps


def alertes_navigation(request):
    map_context = {
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
        "google_maps_enabled": (
            settings.MAP_PROVIDER == "google"
            and bool(settings.GOOGLE_MAPS_API_KEY)
        ),
    }
    if not request.user.is_authenticated:
        return {
            "nav_alertes": [],
            "nav_alertes_non_lues": 0,
            **map_context,
        }

    # Le contrôle côté serveur garantit la création de l'alerte même si
    # JavaScript est bloqué ou si l'onglet était fermé pendant la déconnexion.
    if request.user.is_responsable:
        verifier_alertes_gps()
    alertes = alertes_pour_utilisateur(request.user)
    return {
        "nav_alertes": alertes[:5],
        "nav_alertes_non_lues": alertes.filter(is_read=False).count(),
        **map_context,
    }
