from datetime import timedelta

from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

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
from .services import alertes_pour_utilisateur


class MotoTrackBaseTest(TestCase):
    def setUp(self):
        self.responsable = User.objects.create_user(
            username="admin-test",
            password="TestPass123!",
            role=User.Role.RESPONSABLE,
        )
        self.user_livreur = User.objects.create_user(
            username="livreur-test",
            password="TestPass123!",
            role=User.Role.LIVREUR,
        )
        self.livreur = Livreur.objects.create(
            utilisateur=self.user_livreur,
            nom="Doe",
            prenom="Jane",
            telephone="123",
            adresse="Adresse",
            numero_permis="P-001",
            numero_cni="C-001",
        )
        self.moto = Moto.objects.create(
            immatriculation="TEST-001", marque="Honda", modele="125"
        )
        self.affectation = Affectation.objects.create(
            moto=self.moto, livreur=self.livreur
        )


class AffectationTests(MotoTrackBaseTest):
    def test_moto_ne_peut_pas_avoir_deux_affectations_actives(self):
        autre_user = User.objects.create_user(
            username="autre", password="TestPass123!", role=User.Role.LIVREUR
        )
        autre_livreur = Livreur.objects.create(
            utilisateur=autre_user,
            nom="Autre",
            prenom="Livreur",
            telephone="456",
            adresse="Adresse",
            numero_permis="P-002",
            numero_cni="C-002",
        )
        with self.assertRaises(ValidationError):
            Affectation.objects.create(moto=self.moto, livreur=autre_livreur)

    def test_livreur_inactif_desactive_son_compte(self):
        self.livreur.actif = False
        self.livreur.save()
        self.user_livreur.refresh_from_db()
        self.assertFalse(self.user_livreur.is_active)


class LivreurContractTests(MotoTrackBaseTest):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin-test", password="TestPass123!")

    def test_cdd_exige_des_dates_valides(self):
        self.livreur.type_contrat = Livreur.TypeContrat.CDD
        with self.assertRaises(ValidationError):
            self.livreur.save()

    def test_fiche_livreur_affiche_et_telecharge_le_contrat(self):
        self.livreur.type_contrat = Livreur.TypeContrat.CDD
        self.livreur.date_debut_contrat = timezone.localdate()
        self.livreur.date_fin_contrat = timezone.localdate() + timedelta(days=180)
        self.livreur.document_contrat = SimpleUploadedFile(
            "contrat-test.pdf",
            b"%PDF-1.4 contrat MotoTrack",
            content_type="application/pdf",
        )
        self.livreur.save()

        detail = self.client.get(reverse("livreur-detail", args=[self.livreur.pk]))
        self.assertContains(detail, "Contrat professionnel")
        self.assertContains(detail, "CDD")
        self.assertContains(detail, "Télécharger le contrat")

        download = self.client.get(
            reverse("livreur-contract-download", args=[self.livreur.pk])
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "application/pdf")


class SuppressionTests(MotoTrackBaseTest):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin-test", password="TestPass123!")

    def creer_mission_avec_preuve(self):
        mission = Mission.objects.create(
            nom_client="Client suppression",
            telephone_client="700000000",
            adresse_livraison="Dakar",
            livreur=self.livreur,
            moto=self.moto,
        )
        mission.valider_otp(mission.otp)
        return mission

    def test_suppression_moto_supprime_ses_dependances(self):
        mission = self.creer_mission_avec_preuve()
        PositionGPS.objects.create(
            moto=self.moto,
            latitude="14.7167000",
            longitude="-17.4677000",
        )

        response = self.client.post(reverse("moto-delete", args=[self.moto.pk]))

        self.assertRedirects(response, reverse("moto-list"))
        self.assertFalse(Moto.objects.filter(pk=self.moto.pk).exists())
        self.assertFalse(Mission.objects.filter(pk=mission.pk).exists())
        self.assertFalse(Affectation.objects.filter(pk=self.affectation.pk).exists())
        self.assertFalse(PreuveLivraison.objects.filter(mission_id=mission.pk).exists())

    def test_suppression_livreur_supprime_compte_et_libere_moto(self):
        mission = self.creer_mission_avec_preuve()
        user_id = self.user_livreur.pk

        response = self.client.post(
            reverse("livreur-delete", args=[self.livreur.pk])
        )

        self.assertRedirects(response, reverse("livreur-list"))
        self.assertFalse(Livreur.objects.filter(pk=self.livreur.pk).exists())
        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(Mission.objects.filter(pk=mission.pk).exists())
        self.moto.refresh_from_db()
        self.assertEqual(self.moto.etat, Moto.Etat.DISPONIBLE)


class OTPTests(MotoTrackBaseTest):
    def setUp(self):
        super().setUp()
        self.mission = Mission.objects.create(
            nom_client="Client",
            telephone_client="999",
            adresse_livraison="Destination",
            livreur=self.livreur,
            moto=self.moto,
        )

    def test_otp_est_genere_automatiquement(self):
        self.assertEqual(len(self.mission.otp), 6)
        self.assertTrue(self.mission.otp.isdigit())

    def test_otp_valide_termine_mission_et_cree_preuve(self):
        self.mission.valider_otp(self.mission.otp)
        self.mission.refresh_from_db()
        self.assertEqual(self.mission.statut, Mission.Statut.TERMINEE)
        self.assertTrue(
            PreuveLivraison.objects.filter(mission=self.mission).exists()
        )

    def test_otp_incorrect_est_refuse(self):
        with self.assertRaises(ValidationError):
            self.mission.valider_otp("000000" if self.mission.otp != "000000" else "111111")

    def test_mission_ne_peut_pas_etre_terminee_sans_otp(self):
        self.mission.statut = Mission.Statut.TERMINEE
        with self.assertRaises(ValidationError):
            self.mission.save()


@override_settings(GPS_API_KEY="cle-test")
class GPSTests(MotoTrackBaseTest):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.payload = {
            "moto": self.moto.id,
            "latitude": "-0.3365400",
            "longitude": "6.7273200",
            "date_appareil": "2026-06-13",
            "heure_appareil": "12:00:00",
        }

    def test_api_gps_exige_cle(self):
        response = self.client.post(reverse("gps-create"), self.payload, format="json")
        self.assertEqual(response.status_code, 403)

    def test_api_gps_enregistre_position(self):
        response = self.client.post(
            reverse("gps-create"),
            self.payload,
            format="json",
            HTTP_X_API_KEY="cle-test",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.moto.positions.count(), 1)

    def test_api_gps_accepte_moto_id(self):
        payload = self.payload.copy()
        payload["moto_id"] = payload.pop("moto")
        response = self.client.post(
            reverse("gps-create"),
            payload,
            format="json",
            HTTP_X_API_KEY="cle-test",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.moto.positions.count(), 1)

    def test_api_gps_accepte_immatriculation(self):
        payload = self.payload.copy()
        payload.pop("moto")
        payload["moto_immatriculation"] = self.moto.immatriculation.lower()
        response = self.client.post(
            reverse("gps-create"),
            payload,
            format="json",
            HTTP_X_API_KEY="cle-test",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.moto.positions.count(), 1)

    def test_livreur_ne_peut_pas_creer_moto(self):
        token = Token.objects.create(user=self.user_livreur)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post(
            "/api/motos/",
            {
                "immatriculation": "INTERDIT",
                "marque": "X",
                "modele": "Y",
                "etat": Moto.Etat.DISPONIBLE,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_authentification_retourne_un_token(self):
        response = self.client.post(
            reverse("api-token"),
            {"username": "admin-test", "password": "TestPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)


@override_settings(GPS_API_KEY="cle-alertes", GPS_ALERT_DELAY_MINUTES=10)
class AlertTests(MotoTrackBaseTest):
    def setUp(self):
        super().setUp()
        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.responsable)

    def test_position_hors_zone_cree_une_seule_alerte(self):
        payload = {
            "moto": self.moto.id,
            "latitude": "17.2000000",
            "longitude": "-18.0000000",
        }
        for _ in range(2):
            response = self.api_client.post(
                reverse("gps-create"),
                payload,
                format="json",
                HTTP_X_API_KEY="cle-alertes",
            )
            self.assertEqual(response.status_code, 201)

        alertes = Alert.objects.filter(
            moto=self.moto,
            type=Alert.Type.SORTIE_ZONE,
            is_read=False,
        )
        self.assertEqual(alertes.count(), 1)

    def test_commande_gps_cree_alerte_deconnexion(self):
        position = PositionGPS.objects.create(
            moto=self.moto,
            latitude="14.7167000",
            longitude="-17.4677000",
        )
        PositionGPS.objects.filter(pk=position.pk).update(
            recue_le=timezone.now() - timedelta(minutes=15)
        )

        call_command("check_gps_alerts")

        self.assertTrue(
            Alert.objects.filter(
                moto=self.moto,
                type=Alert.Type.GPS_DECONNECTE,
                is_read=False,
            ).exists()
        )

    def test_alerte_gps_lue_n_est_pas_recreee_pendant_meme_incident(self):
        position = PositionGPS.objects.create(
            moto=self.moto,
            latitude="14.7167000",
            longitude="-17.4677000",
        )
        PositionGPS.objects.filter(pk=position.pk).update(
            recue_le=timezone.now() - timedelta(minutes=15)
        )
        call_command("check_gps_alerts")
        alerte = Alert.objects.get(
            moto=self.moto,
            type=Alert.Type.GPS_DECONNECTE,
        )
        alerte.is_read = True
        alerte.save(update_fields=["is_read"])

        call_command("check_gps_alerts")

        self.assertEqual(
            Alert.objects.filter(
                moto=self.moto,
                type=Alert.Type.GPS_DECONNECTE,
            ).count(),
            1,
        )

    def test_nouvelle_deconnexion_apres_reconnexion_cree_nouvelle_alerte(self):
        ancienne_position = PositionGPS.objects.create(
            moto=self.moto,
            latitude="14.7167000",
            longitude="-17.4677000",
        )
        PositionGPS.objects.filter(pk=ancienne_position.pk).update(
            recue_le=timezone.now() - timedelta(minutes=15)
        )
        call_command("check_gps_alerts")
        premiere_alerte = Alert.objects.get(
            moto=self.moto,
            type=Alert.Type.GPS_DECONNECTE,
        )
        Alert.objects.filter(pk=premiere_alerte.pk).update(
            is_read=True,
            date=timezone.now() - timedelta(minutes=30),
        )

        nouvelle_position = PositionGPS.objects.create(
            moto=self.moto,
            latitude="14.7170000",
            longitude="-17.4680000",
        )
        PositionGPS.objects.filter(pk=nouvelle_position.pk).update(
            recue_le=timezone.now() - timedelta(minutes=15)
        )
        call_command("check_gps_alerts")

        self.assertEqual(
            Alert.objects.filter(
                moto=self.moto,
                type=Alert.Type.GPS_DECONNECTE,
            ).count(),
            2,
        )

    def test_chargement_page_responsable_detecte_gps_deconnecte(self):
        position = PositionGPS.objects.create(
            moto=self.moto,
            latitude="14.7167000",
            longitude="-17.4677000",
        )
        PositionGPS.objects.filter(pk=position.pk).update(
            recue_le=timezone.now() - timedelta(minutes=15)
        )
        self.client.login(username="admin-test", password="TestPass123!")

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Alert.objects.filter(
                moto=self.moto,
                type=Alert.Type.GPS_DECONNECTE,
                is_read=False,
            ).exists()
        )

    def test_validation_otp_cree_alerte_commande(self):
        mission = Mission.objects.create(
            nom_client="Client OTP",
            telephone_client="700000000",
            adresse_livraison="Dakar",
            livreur=self.livreur,
            moto=self.moto,
        )
        mission.valider_otp(mission.otp)

        self.assertTrue(
            Alert.objects.filter(
                mission=mission,
                type=Alert.Type.VALIDATION_COMMANDE,
            ).exists()
        )

    def test_api_compte_et_marque_alerte_comme_lue(self):
        alerte = Alert.objects.create(
            moto=self.moto,
            type=Alert.Type.SORTIE_ZONE,
            message="Moto hors zone.",
        )
        count_response = self.api_client.get(reverse("alert-unread-count"))
        self.assertEqual(count_response.status_code, 200)
        self.assertEqual(count_response.data["unread_count"], 1)

        read_response = self.api_client.post(
            f"/api/alerts/{alerte.pk}/mark-read/",
            {},
            format="json",
        )
        self.assertEqual(read_response.status_code, 200)
        alerte.refresh_from_db()
        self.assertTrue(alerte.is_read)

    def test_suppression_api_autorisee_uniquement_apres_lecture(self):
        alerte = Alert.objects.create(
            moto=self.moto,
            type=Alert.Type.SORTIE_ZONE,
            message="Alerte à supprimer.",
        )
        refused = self.api_client.post(
            f"/api/alerts/{alerte.pk}/delete-read/",
            {},
            format="json",
        )
        self.assertEqual(refused.status_code, 400)

        alerte.is_read = True
        alerte.save(update_fields=["is_read"])
        deleted = self.api_client.post(
            f"/api/alerts/{alerte.pk}/delete-read/",
            {},
            format="json",
        )
        self.assertEqual(deleted.status_code, 204)
        alerte.refresh_from_db()
        self.assertTrue(alerte.is_archived)
        self.assertFalse(
            alertes_pour_utilisateur(self.responsable).filter(pk=alerte.pk).exists()
        )

    def test_suppression_alerte_gps_lue_ne_recree_pas_meme_incident(self):
        position = PositionGPS.objects.create(
            moto=self.moto,
            latitude="14.7167000",
            longitude="-17.4677000",
        )
        PositionGPS.objects.filter(pk=position.pk).update(
            recue_le=timezone.now() - timedelta(minutes=15)
        )
        call_command("check_gps_alerts")
        alerte = Alert.objects.get(
            moto=self.moto,
            type=Alert.Type.GPS_DECONNECTE,
        )
        alerte.is_read = True
        alerte.is_archived = True
        alerte.save(update_fields=["is_read", "is_archived"])

        call_command("check_gps_alerts")

        self.assertEqual(
            Alert.objects.filter(
                moto=self.moto,
                type=Alert.Type.GPS_DECONNECTE,
            ).count(),
            1,
        )

    def test_api_mission_retourne_destination_et_derniere_position(self):
        mission = Mission.objects.create(
            nom_client="Mamadou Diop",
            telephone_client="770000000",
            adresse_livraison="Bambey",
            destination_latitude="14.6928000",
            destination_longitude="-16.4665000",
            livreur=self.livreur,
            moto=self.moto,
        )
        PositionGPS.objects.create(
            moto=self.moto,
            latitude="14.6910000",
            longitude="-16.4657000",
        )

        response = self.api_client.get(f"/api/missions/{mission.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["destination_latitude"]), "14.6928000")
        self.assertEqual(str(response.data["destination_longitude"]), "-16.4665000")
        self.assertEqual(response.data["moto_detail"]["immatriculation"], "TEST-001")
        self.assertIsNotNone(response.data["last_position"])


class ResponsableProfileTests(MotoTrackBaseTest):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin-test", password="TestPass123!")

    def test_responsable_peut_modifier_son_profil(self):
        response = self.client.post(
            reverse("responsable-profile"),
            {
                "action": "profile",
                "profile-username": "admin-test",
                "profile-first_name": "Awa",
                "profile-last_name": "Diop",
                "profile-email": "awa@example.com",
                "profile-telephone": "+221770000000",
            },
        )
        self.assertRedirects(response, reverse("responsable-profile"))
        self.responsable.refresh_from_db()
        self.assertEqual(self.responsable.first_name, "Awa")
        self.assertEqual(self.responsable.telephone, "+221770000000")

    def test_tableau_de_bord_affiche_les_nouvelles_statistiques(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Missions annulées")
        self.assertContains(response, "Missions en attente")
        self.assertContains(response, "Livreurs inactifs")

    def test_liste_missions_propose_voir_details(self):
        Mission.objects.create(
            nom_client="Client détail",
            telephone_client="777",
            adresse_livraison="Dakar",
            livreur=self.livreur,
            moto=self.moto,
        )
        response = self.client.get(reverse("mission-list"))
        self.assertContains(response, "Voir détails")


@override_settings(RESPONSABLE_REGISTRATION_CODE="CODE-BAOL")
class AccountManagementTests(MotoTrackBaseTest):
    def test_creation_compte_responsable_depuis_authentification(self):
        response = self.client.post(
            reverse("responsable-register"),
            {
                "username": "nouveau-responsable",
                "first_name": "Moussa",
                "last_name": "Fall",
                "email": "moussa@example.com",
                "telephone": "770000001",
                "password1": "MotDePasseSolide2026!",
                "password2": "MotDePasseSolide2026!",
                "code_inscription": "CODE-BAOL",
            },
        )
        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="nouveau-responsable")
        self.assertEqual(user.role, User.Role.RESPONSABLE)

    def test_creation_livreur_enregistre_age(self):
        self.client.login(username="admin-test", password="TestPass123!")
        response = self.client.post(
            reverse("livreur-create"),
            {
                "username": "livreur-age",
                "email": "livreur-age@example.com",
                "password1": "MotDePasseSolide2026!",
                "password2": "MotDePasseSolide2026!",
                "nom": "Ndiaye",
                "prenom": "Aminata",
                "age": 29,
                "telephone": "770000002",
                "adresse": "Dakar",
                "numero_permis": "PERMIS-AGE",
                "numero_cni": "CNI-AGE",
                "type_contrat": Livreur.TypeContrat.CDI,
                "actif": "on",
            },
        )
        livreur = Livreur.objects.get(utilisateur__username="livreur-age")
        self.assertRedirects(response, reverse("livreur-list"))
        self.assertEqual(livreur.age, 29)

    def test_responsable_reinitialise_mot_de_passe_livreur(self):
        self.client.login(username="admin-test", password="TestPass123!")
        response = self.client.post(
            reverse("livreur-password-reset", args=[self.livreur.pk]),
            {
                "new_password1": "NouveauMotDePasse2026!",
                "new_password2": "NouveauMotDePasse2026!",
            },
        )
        self.assertRedirects(
            response, reverse("livreur-detail", args=[self.livreur.pk])
        )
        self.user_livreur.refresh_from_db()
        self.assertTrue(
            self.user_livreur.check_password("NouveauMotDePasse2026!")
        )

    def test_fiche_livreur_affiche_identifiant_sans_mot_de_passe(self):
        self.client.login(username="admin-test", password="TestPass123!")
        response = self.client.get(
            reverse("livreur-detail", args=[self.livreur.pk])
        )
        self.assertContains(response, self.user_livreur.username)
        self.assertContains(response, "Protégé et non affichable")
        self.assertNotContains(response, "TestPass123!")


class LivreurSpaceTests(MotoTrackBaseTest):
    def setUp(self):
        super().setUp()
        self.mission = Mission.objects.create(
            nom_client="Client Livreur",
            telephone_client="771234567",
            adresse_livraison="Bambey",
            destination_latitude="14.6928000",
            destination_longitude="-16.4665000",
            livreur=self.livreur,
            moto=self.moto,
        )
        self.client.login(username="livreur-test", password="TestPass123!")

    def test_connexion_redirige_vers_tableau_de_bord_livreur(self):
        self.client.logout()
        response = self.client.post(
            reverse("login"),
            {"username": "livreur-test", "password": "TestPass123!"},
        )
        self.assertRedirects(response, reverse("livreur-dashboard"))

    def test_permissions_separent_responsable_et_livreur(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)
        self.client.logout()
        self.client.login(username="admin-test", password="TestPass123!")
        self.assertEqual(
            self.client.get(reverse("livreur-dashboard")).status_code, 403
        )

    def test_tableau_de_bord_et_profil_livreur_en_lecture_seule(self):
        response = self.client.get(reverse("livreur-dashboard"))
        self.assertContains(response, "MOTOTRACK")
        self.assertContains(response, "Client Livreur")
        self.assertNotContains(response, "Ma position")

        profile_response = self.client.get(reverse("livreur-profile"))
        self.assertContains(profile_response, "Profil sécurisé")
        self.assertContains(profile_response, self.livreur.numero_permis)
        response = self.client.post(
            reverse("livreur-profile"),
            {
                "action": "profile",
                "profile-telephone": "770001122",
                "profile-adresse": "Nouvelle adresse",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.livreur.refresh_from_db()
        self.assertEqual(self.livreur.telephone, "123")
        self.assertEqual(self.livreur.numero_permis, "P-001")
        api_response = self.client.patch(
            reverse("api-livreur-profile"),
            {"telephone": "770001122"},
            content_type="application/json",
        )
        self.assertEqual(api_response.status_code, 405)

    def test_livreur_ne_voit_pas_mission_autrui(self):
        autre_user = User.objects.create_user(
            username="livreur-autre",
            password="TestPass123!",
            role=User.Role.LIVREUR,
        )
        autre_livreur = Livreur.objects.create(
            utilisateur=autre_user,
            nom="Autre",
            prenom="Livreur",
            telephone="700",
            adresse="Adresse",
            numero_permis="P-900",
            numero_cni="C-900",
        )
        autre_moto = Moto.objects.create(
            immatriculation="AUTRE-001", marque="Yamaha", modele="YBR"
        )
        Affectation.objects.create(moto=autre_moto, livreur=autre_livreur)
        autre_mission = Mission.objects.create(
            nom_client="Mission privée",
            telephone_client="700",
            adresse_livraison="Dakar",
            livreur=autre_livreur,
            moto=autre_moto,
        )
        self.assertEqual(
            self.client.get(
                reverse("mission-detail", args=[autre_mission.pk])
            ).status_code,
            403,
        )
        api_response = self.client.get(reverse("api-livreur-missions"))
        ids = [mission["id"] for mission in api_response.json()]
        self.assertIn(self.mission.pk, ids)
        self.assertNotIn(autre_mission.pk, ids)

    def test_validation_otp_historique_et_pdf(self):
        response = self.client.post(
            reverse("mission-otp", args=[self.mission.pk]),
            {"otp": self.mission.otp},
        )
        self.assertRedirects(
            response, reverse("mission-detail", args=[self.mission.pk])
        )
        self.mission.refresh_from_db()
        self.assertEqual(self.mission.statut, Mission.Statut.TERMINEE)
        self.assertContains(
            self.client.get(reverse("livreur-livraisons")), "Client Livreur"
        )
        pdf_response = self.client.get(
            reverse("livreur-preuve-pdf", args=[self.mission.preuve.pk])
        )
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")

    def test_alertes_mission_et_position_gps_filtrees(self):
        self.assertTrue(
            Alert.objects.filter(
                mission=self.mission,
                type=Alert.Type.MISSION_ASSIGNEE,
            ).exists()
        )
        PositionGPS.objects.create(
            moto=self.moto,
            latitude="14.6910000",
            longitude="-16.4657000",
        )
        Alert.objects.create(
            moto=self.moto,
            type=Alert.Type.GPS_DECONNECTE,
            message="GPS déconnecté à masquer.",
        )
        alert_response = self.client.get(reverse("alert-list"))
        self.assertContains(alert_response, "Nouvelle mission assignée")
        self.assertNotContains(alert_response, "GPS déconnecté à masquer")

        self.mission.statut = Mission.Statut.ANNULEE
        self.mission.save()
        alert_response = self.client.get(reverse("alert-list"))
        self.assertContains(alert_response, "La mission")
        self.assertContains(alert_response, "a été annulée")
