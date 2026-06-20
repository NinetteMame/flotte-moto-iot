from django.contrib.auth.views import LogoutView
from django.urls import path

from . import web_views

urlpatterns = [
    path("", web_views.home, name="home"),
    path("connexion/", web_views.MotoTrackLoginView.as_view(), name="login"),
    path(
        "inscription-responsable/",
        web_views.responsable_register,
        name="responsable-register",
    ),
    path("deconnexion/", LogoutView.as_view(), name="logout"),
    path("tableau-de-bord/", web_views.dashboard, name="dashboard"),
    path("motos/", web_views.moto_list, name="moto-list"),
    path("motos/ajouter/", web_views.moto_form, name="moto-create"),
    path("motos/<int:pk>/modifier/", web_views.moto_form, name="moto-update"),
    path("motos/<int:pk>/supprimer/", web_views.moto_delete, name="moto-delete"),
    path("livreurs/", web_views.livreur_list, name="livreur-list"),
    path("livreurs/ajouter/", web_views.livreur_create, name="livreur-create"),
    path(
        "livreurs/<int:pk>/",
        web_views.livreur_detail,
        name="livreur-detail",
    ),
    path(
        "livreurs/<int:pk>/contrat/",
        web_views.livreur_contrat_download,
        name="livreur-contract-download",
    ),
    path(
        "livreurs/<int:pk>/modifier/",
        web_views.livreur_update,
        name="livreur-update",
    ),
    path(
        "livreurs/<int:pk>/mot-de-passe/",
        web_views.livreur_password_reset,
        name="livreur-password-reset",
    ),
    path(
        "livreurs/<int:pk>/supprimer/",
        web_views.livreur_delete,
        name="livreur-delete",
    ),
    path("affectations/", web_views.affectation_list, name="affectation-list"),
    path(
        "affectations/ajouter/",
        web_views.affectation_form,
        name="affectation-create",
    ),
    path(
        "affectations/<int:pk>/modifier/",
        web_views.affectation_form,
        name="affectation-update",
    ),
    path(
        "affectations/<int:pk>/supprimer/",
        web_views.affectation_delete,
        name="affectation-delete",
    ),
    path("missions/", web_views.mission_list, name="mission-list"),
    path("missions/ajouter/", web_views.mission_form, name="mission-create"),
    path("missions/<int:pk>/", web_views.mission_detail, name="mission-detail"),
    path(
        "missions/<int:pk>/modifier/",
        web_views.mission_form,
        name="mission-update",
    ),
    path(
        "missions/<int:pk>/supprimer/",
        web_views.mission_delete,
        name="mission-delete",
    ),
    path(
        "missions/<int:pk>/valider-otp/",
        web_views.valider_otp,
        name="mission-otp",
    ),
    path("carte-gps/", web_views.gps_map, name="gps-map"),
    path("preuves/", web_views.preuve_list, name="preuve-list"),
    path("alertes/", web_views.alert_list, name="alert-list"),
    path(
        "alertes/<int:pk>/marquer-lue/",
        web_views.alert_mark_read,
        name="alert-mark-read",
    ),
    path(
        "alertes/<int:pk>/supprimer/",
        web_views.alert_delete,
        name="alert-delete",
    ),
    path(
        "alertes/verifier-gps/",
        web_views.alert_check_gps,
        name="alert-check-gps",
    ),
    path(
        "mon-profil/",
        web_views.responsable_profile,
        name="responsable-profile",
    ),
    path(
        "espace-livreur/tableau-de-bord/",
        web_views.livreur_dashboard,
        name="livreur-dashboard",
    ),
    path("espace-livreur/", web_views.livreur_missions, name="livreur-missions"),
    path(
        "espace-livreur/profil/",
        web_views.livreur_profile,
        name="livreur-profile",
    ),
    path(
        "espace-livreur/ma-moto/",
        web_views.livreur_moto,
        name="livreur-moto",
    ),
    path(
        "espace-livreur/livraisons/",
        web_views.livreur_livraisons,
        name="livreur-livraisons",
    ),
    path(
        "espace-livreur/preuves/<int:pk>/",
        web_views.preuve_livraison_detail,
        name="livreur-preuve",
    ),
    path(
        "espace-livreur/preuves/<int:pk>/pdf/",
        web_views.preuve_livraison_pdf,
        name="livreur-preuve-pdf",
    ),
]
