from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from tracking.models import Affectation, Livreur, Mission, Moto, PositionGPS, User


class Command(BaseCommand):
    help = "Crée un jeu de données simple pour la démonstration de MotoTrack."

    def handle(self, *args, **options):
        responsable, created = User.objects.get_or_create(
            username="responsable",
            defaults={
                "first_name": "Amina",
                "last_name": "Responsable",
                "role": User.Role.RESPONSABLE,
                "is_staff": True,
            },
        )
        if created:
            responsable.set_password("MotoTrack2026!")
            responsable.save()

        user_livreur, created = User.objects.get_or_create(
            username="livreur",
            defaults={
                "first_name": "Samuel",
                "last_name": "Costa",
                "role": User.Role.LIVREUR,
            },
        )
        if created:
            user_livreur.set_password("MotoTrack2026!")
            user_livreur.save()

        livreur, _ = Livreur.objects.get_or_create(
            utilisateur=user_livreur,
            defaults={
                "nom": "Costa",
                "prenom": "Samuel",
                "telephone": "+239 990 00 00",
                "adresse": "São Tomé",
                "numero_permis": "PERMIS-DEMO-001",
                "numero_cni": "CNI-DEMO-001",
            },
        )
        moto, _ = Moto.objects.get_or_create(
            immatriculation="STP-001",
            defaults={
                "marque": "Honda",
                "modele": "CB125F",
                "etat": Moto.Etat.DISPONIBLE,
            },
        )
        Affectation.objects.get_or_create(
            moto=moto,
            livreur=livreur,
            active=True,
            defaults={"notes": "Affectation de démonstration"},
        )
        Mission.objects.get_or_create(
            nom_client="Client Démonstration",
            telephone_client="+239 980 00 00",
            adresse_livraison="Centre-ville, São Tomé",
            livreur=livreur,
            moto=moto,
            defaults={
                "description_lieu": "Bâtiment bleu près du marché.",
                "statut": Mission.Statut.EN_COURS,
            },
        )
        if not moto.positions.exists():
            for index in range(3):
                PositionGPS.objects.create(
                    moto=moto,
                    latitude=14.716700 + index * 0.001,
                    longitude=-17.467700 + index * 0.001,
                    date_appareil=timezone.localdate(),
                    heure_appareil=(timezone.now() - timedelta(minutes=index)).time(),
                )

        self.stdout.write(self.style.SUCCESS("Données de démonstration créées."))
        self.stdout.write("Responsable : responsable / MotoTrack2026!")
        self.stdout.write("Livreur : livreur / MotoTrack2026!")
