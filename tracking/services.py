from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Alert, Moto


SENEGAL_LAT_MIN = 12.0
SENEGAL_LAT_MAX = 16.8
SENEGAL_LNG_MIN = -17.7
SENEGAL_LNG_MAX = -11.3


def resume_suppression_moto(moto):
    return [
        ("Affectations", moto.affectations.count()),
        ("Missions", moto.missions.count()),
        ("Positions GPS", moto.positions.count()),
        ("Preuves de livraison", moto.preuves.count()),
    ]


def resume_suppression_livreur(livreur):
    return [
        ("Affectations", livreur.affectations.count()),
        ("Missions", livreur.missions.count()),
        ("Preuves de livraison", livreur.preuves.count()),
        ("Compte utilisateur", 1),
    ]


@transaction.atomic
def supprimer_moto_et_dependances(moto):
    moto.missions.all().delete()
    for affectation in list(moto.affectations.all()):
        affectation.delete()
    moto.delete()


@transaction.atomic
def supprimer_livreur_et_dependances(livreur):
    motos_affectees = [
        affectation.moto
        for affectation in livreur.affectations.select_related("moto")
    ]
    livreur.missions.all().delete()
    for affectation in list(livreur.affectations.all()):
        affectation.delete()
    livreur.utilisateur.delete()

    for moto in motos_affectees:
        if (
            moto.etat == Moto.Etat.AFFECTEE
            and not moto.affectations.filter(active=True).exists()
        ):
            moto.etat = Moto.Etat.DISPONIBLE
            moto.save(update_fields=["etat"])


def position_dans_zone_senegal(latitude, longitude):
    latitude = float(latitude)
    longitude = float(longitude)
    return (
        SENEGAL_LAT_MIN <= latitude <= SENEGAL_LAT_MAX
        and SENEGAL_LNG_MIN <= longitude <= SENEGAL_LNG_MAX
    )


def traiter_nouvelle_position(position):
    Alert.objects.filter(
        moto=position.moto,
        type=Alert.Type.GPS_DECONNECTE,
        is_read=False,
    ).update(is_read=True)

    if position_dans_zone_senegal(position.latitude, position.longitude):
        return None

    alerte, _ = Alert.objects.get_or_create(
        moto=position.moto,
        type=Alert.Type.SORTIE_ZONE,
        is_read=False,
        defaults={
            "message": (
                f"La moto {position.moto.immatriculation} est sortie "
                "de la zone autorisée."
            )
        },
    )
    return alerte


def verifier_alertes_gps(delai_minutes=None):
    delai = delai_minutes or getattr(settings, "GPS_ALERT_DELAY_MINUTES", 10)
    limite = timezone.now() - timedelta(minutes=delai)
    motos = Moto.objects.filter(
        Q(etat__in=[Moto.Etat.AFFECTEE, Moto.Etat.EN_MISSION])
        | Q(affectations__active=True)
    ).distinct()

    alertes_creees = []
    for moto in motos:
        derniere_position = moto.positions.first()
        if derniere_position:
            est_deconnectee = derniere_position.recue_le < limite
            reference_incident = derniere_position.recue_le
        else:
            affectation = moto.affectations.filter(active=True).first()
            reference_incident = affectation.date_debut if affectation else moto.cree_le
            est_deconnectee = reference_incident < limite

        if not est_deconnectee:
            continue

        # Une alerte lue reste liée à la déconnexion actuelle. Une nouvelle
        # alerte ne sera créée qu'après réception d'une nouvelle position,
        # suivie d'une autre période de silence.
        incident_deja_signale = Alert.objects.filter(
            moto=moto,
            type=Alert.Type.GPS_DECONNECTE,
            date__gte=reference_incident,
        ).exists()
        if incident_deja_signale:
            continue

        alerte = Alert.objects.create(
            moto=moto,
            type=Alert.Type.GPS_DECONNECTE,
            message=(
                "GPS déconnecté : aucune position reçue pour la moto "
                f"{moto.immatriculation} depuis plus de {delai} minutes."
            ),
        )
        alertes_creees.append(alerte)

    return alertes_creees


def alertes_pour_utilisateur(user):
    queryset = Alert.objects.filter(is_archived=False).select_related(
        "moto", "mission"
    )
    if user.is_responsable:
        return queryset
    return queryset.filter(
        mission__livreur__utilisateur=user,
        type__in=[
            Alert.Type.MISSION_ASSIGNEE,
            Alert.Type.MISSION_ANNULEE,
        ],
    ).distinct()
