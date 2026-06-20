from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import (
    AffectationViewSet,
    AlertViewSet,
    ChangePasswordView,
    CurrentUserView,
    DernieresPositionsView,
    GPSPositionCreateView,
    HistoriqueGPSView,
    LivreurHistoriqueAPIView,
    LivreurMissionsAPIView,
    LivreurProfileAPIView,
    LoginTokenView,
    LivreurViewSet,
    MissionViewSet,
    MotoViewSet,
    PreuveViewSet,
    RegisterManagerView,
)

router = DefaultRouter()
router.register("motos", MotoViewSet)
router.register("livreurs", LivreurViewSet)
router.register("affectations", AffectationViewSet)
router.register("missions", MissionViewSet, basename="mission")
router.register("preuves", PreuveViewSet)
router.register("alerts", AlertViewSet, basename="alert")

urlpatterns = [
    path("auth/token/", LoginTokenView.as_view(), name="api-token"),
    path("auth/login/", LoginTokenView.as_view(), name="api-login"),
    path("auth/me/", CurrentUserView.as_view(), name="api-current-user"),
    path("auth/register/", RegisterManagerView.as_view(), name="api-register"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="api-change-password"),
    path(
        "livreur/profil/",
        LivreurProfileAPIView.as_view(),
        name="api-livreur-profile",
    ),
    path(
        "livreur/missions/",
        LivreurMissionsAPIView.as_view(),
        name="api-livreur-missions",
    ),
    path(
        "livreur/livraisons/",
        LivreurHistoriqueAPIView.as_view(),
        name="api-livreur-history",
    ),
    path("gps/positions/", GPSPositionCreateView.as_view(), name="gps-create"),
    path(
        "gps/dernieres-positions/",
        DernieresPositionsView.as_view(),
        name="gps-latest",
    ),
    path(
        "gps/motos/<int:moto_id>/historique/",
        HistoriqueGPSView.as_view(),
        name="gps-history",
    ),
    path("", include(router.urls)),
]
