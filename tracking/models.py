import secrets

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        RESPONSABLE = "RESPONSABLE", "Responsable"
        LIVREUR = "LIVREUR", "Livreur"

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.RESPONSABLE
    )
    telephone = models.CharField(max_length=30, blank=True)

    @property
    def is_responsable(self):
        return self.is_superuser or self.role == self.Role.RESPONSABLE


class Moto(models.Model):
    class Etat(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        AFFECTEE = "AFFECTEE", "Affectée"
        EN_MISSION = "EN_MISSION", "En mission"
        HORS_SERVICE = "HORS_SERVICE", "Hors service"

    immatriculation = models.CharField(max_length=30, unique=True)
    marque = models.CharField(max_length=80)
    modele = models.CharField(max_length=80)
    etat = models.CharField(
        max_length=20, choices=Etat.choices, default=Etat.DISPONIBLE
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["immatriculation"]

    def __str__(self):
        return f"{self.immatriculation} - {self.marque} {self.modele}"


class Livreur(models.Model):
    class TypeContrat(models.TextChoices):
        CDD = "CDD", "CDD"
        CDI = "CDI", "CDI"

    utilisateur = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profil_livreur"
    )
    nom = models.CharField(max_length=80)
    prenom = models.CharField(max_length=80)
    age = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(18), MaxValueValidator(80)],
    )
    telephone = models.CharField(max_length=30)
    adresse = models.TextField()
    numero_permis = models.CharField(max_length=60, unique=True)
    numero_cni = models.CharField(max_length=60, unique=True)
    photo = models.ImageField(upload_to="livreurs/", blank=True, null=True)
    type_contrat = models.CharField(
        max_length=3,
        choices=TypeContrat.choices,
        default=TypeContrat.CDI,
    )
    date_debut_contrat = models.DateField(blank=True, null=True)
    date_fin_contrat = models.DateField(blank=True, null=True)
    document_contrat = models.FileField(
        upload_to="contrats/",
        blank=True,
        null=True,
    )
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.prenom} {self.nom}"

    def clean(self):
        if self.type_contrat == self.TypeContrat.CDD:
            if not self.date_debut_contrat or not self.date_fin_contrat:
                raise ValidationError(
                    "Un contrat CDD exige une date de début et une date de fin."
                )
            if self.date_fin_contrat < self.date_debut_contrat:
                raise ValidationError(
                    {"date_fin_contrat": "La date de fin doit suivre la date de début."}
                )
        elif self.date_fin_contrat:
            raise ValidationError(
                {"date_fin_contrat": "Un contrat CDI ne possède pas de date de fin."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        self.utilisateur.role = User.Role.LIVREUR
        self.utilisateur.is_active = self.actif
        self.utilisateur.save(update_fields=["role", "is_active"])
        super().save(*args, **kwargs)


class Affectation(models.Model):
    moto = models.ForeignKey(
        Moto, on_delete=models.PROTECT, related_name="affectations"
    )
    livreur = models.ForeignKey(
        Livreur, on_delete=models.PROTECT, related_name="affectations"
    )
    date_debut = models.DateTimeField(default=timezone.now)
    date_fin = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_debut"]
        constraints = [
            models.UniqueConstraint(
                fields=["moto"],
                condition=Q(active=True),
                name="unique_moto_affectation_active",
            ),
            models.UniqueConstraint(
                fields=["livreur"],
                condition=Q(active=True),
                name="unique_livreur_affectation_active",
            ),
        ]

    def __str__(self):
        return f"{self.moto.immatriculation} → {self.livreur}"

    def clean(self):
        if self.active:
            moto_occupee = Affectation.objects.filter(
                moto=self.moto, active=True
            ).exclude(pk=self.pk)
            livreur_occupe = Affectation.objects.filter(
                livreur=self.livreur, active=True
            ).exclude(pk=self.pk)
            if moto_occupee.exists():
                raise ValidationError(
                    {"moto": "Cette moto possède déjà une affectation active."}
                )
            if livreur_occupe.exists():
                raise ValidationError(
                    {"livreur": "Ce livreur possède déjà une affectation active."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.active and self.moto.etat == Moto.Etat.DISPONIBLE:
                self.moto.etat = Moto.Etat.AFFECTEE
                self.moto.save(update_fields=["etat"])
            elif not self.active:
                has_other = self.moto.affectations.filter(active=True).exclude(
                    pk=self.pk
                )
                if not has_other.exists() and self.moto.etat == Moto.Etat.AFFECTEE:
                    self.moto.etat = Moto.Etat.DISPONIBLE
                    self.moto.save(update_fields=["etat"])

    def delete(self, *args, **kwargs):
        moto = self.moto
        result = super().delete(*args, **kwargs)
        if (
            not moto.affectations.filter(active=True).exists()
            and moto.etat == Moto.Etat.AFFECTEE
        ):
            moto.etat = Moto.Etat.DISPONIBLE
            moto.save(update_fields=["etat"])
        return result


class Mission(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        EN_COURS = "EN_COURS", "En cours"
        TERMINEE = "TERMINEE", "Terminée"
        ANNULEE = "ANNULEE", "Annulée"

    nom_client = models.CharField(max_length=120)
    telephone_client = models.CharField(max_length=30)
    adresse_livraison = models.TextField()
    description_lieu = models.TextField(blank=True)
    destination_latitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )
    destination_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )
    livreur = models.ForeignKey(
        Livreur, on_delete=models.PROTECT, related_name="missions"
    )
    moto = models.ForeignKey(Moto, on_delete=models.PROTECT, related_name="missions")
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE
    )
    otp = models.CharField(max_length=6, editable=False)
    otp_valide_le = models.DateTimeField(blank=True, null=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-cree_le"]

    def __str__(self):
        return f"Mission #{self.pk or 'nouvelle'} - {self.nom_client}"

    @staticmethod
    def generer_otp():
        return f"{secrets.randbelow(1_000_000):06d}"

    def clean(self):
        if self.livreur_id and self.moto_id:
            correspond = Affectation.objects.filter(
                livreur_id=self.livreur_id, moto_id=self.moto_id, active=True
            ).exists()
            if not correspond:
                raise ValidationError(
                    "La moto et le livreur doivent avoir une affectation active commune."
                )
        if self.statut == self.Statut.TERMINEE and not self.otp_valide_le:
            raise ValidationError(
                "Une mission ne peut être terminée qu'après validation de l'OTP."
            )

        destination_complete = (
            self.destination_latitude is not None
            and self.destination_longitude is not None
        )
        destination_partielle = (
            self.destination_latitude is None
        ) != (
            self.destination_longitude is None
        )
        if destination_partielle:
            raise ValidationError(
                "La latitude et la longitude de destination doivent être renseignées ensemble."
            )
        if destination_complete and not (
            12.0 <= float(self.destination_latitude) <= 16.8
            and -17.7 <= float(self.destination_longitude) <= -11.3
        ):
            raise ValidationError(
                "La destination doit être située dans la zone autorisée du Sénégal."
            )

    def save(self, *args, **kwargs):
        ancienne = None
        if self.pk:
            ancienne = Mission.objects.filter(pk=self.pk).values(
                "statut", "livreur_id"
            ).first()
        if not self.otp:
            self.otp = self.generer_otp()
        self.full_clean()
        super().save(*args, **kwargs)
        if ancienne is None:
            Alert.objects.get_or_create(
                mission=self,
                type=Alert.Type.MISSION_ASSIGNEE,
                defaults={
                    "moto": self.moto,
                    "message": f"Nouvelle mission assignée : mission #{self.pk}.",
                },
            )
        elif (
            ancienne["statut"] != self.Statut.ANNULEE
            and self.statut == self.Statut.ANNULEE
        ):
            Alert.objects.get_or_create(
                mission=self,
                type=Alert.Type.MISSION_ANNULEE,
                defaults={
                    "moto": self.moto,
                    "message": f"La mission #{self.pk} a été annulée.",
                },
            )

    def valider_otp(self, code):
        if self.statut in [self.Statut.TERMINEE, self.Statut.ANNULEE]:
            raise ValidationError("Cette mission ne peut plus être validée.")
        if not secrets.compare_digest(self.otp, str(code).strip()):
            raise ValidationError("OTP incorrect.")

        with transaction.atomic():
            self.statut = self.Statut.TERMINEE
            self.otp_valide_le = timezone.now()
            self.save(update_fields=["statut", "otp_valide_le", "modifie_le"])
            preuve, _ = PreuveLivraison.objects.get_or_create(
                mission=self,
                defaults={
                    "livreur": self.livreur,
                    "moto": self.moto,
                    "client": self.nom_client,
                    "otp_valide": self.otp,
                    "valide_le": self.otp_valide_le,
                },
            )
            Alert.objects.get_or_create(
                mission=self,
                type=Alert.Type.VALIDATION_COMMANDE,
                defaults={
                    "moto": self.moto,
                    "message": f"La mission #{self.pk} a été validée avec succès.",
                },
            )
        return preuve


class PositionGPS(models.Model):
    moto = models.ForeignKey(Moto, on_delete=models.CASCADE, related_name="positions")
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    date_appareil = models.DateField(blank=True, null=True)
    heure_appareil = models.TimeField(blank=True, null=True)
    recue_le = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-recue_le"]
        indexes = [models.Index(fields=["moto", "-recue_le"])]

    def __str__(self):
        return f"{self.moto.immatriculation}: {self.latitude}, {self.longitude}"


class PreuveLivraison(models.Model):
    mission = models.OneToOneField(
        Mission, on_delete=models.CASCADE, related_name="preuve"
    )
    livreur = models.ForeignKey(
        Livreur, on_delete=models.PROTECT, related_name="preuves"
    )
    moto = models.ForeignKey(Moto, on_delete=models.PROTECT, related_name="preuves")
    client = models.CharField(max_length=120)
    otp_valide = models.CharField(max_length=6)
    valide_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-valide_le"]

    def __str__(self):
        return f"Preuve mission #{self.mission_id}"


class Alert(models.Model):
    class Type(models.TextChoices):
        GPS_DECONNECTE = "GPS_DECONNECTE", "GPS déconnecté"
        SORTIE_ZONE = "SORTIE_ZONE", "Sortie de zone"
        VALIDATION_COMMANDE = "VALIDATION_COMMANDE", "Validation de commande"
        MISSION_ASSIGNEE = "MISSION_ASSIGNEE", "Mission assignée"
        MISSION_ANNULEE = "MISSION_ANNULEE", "Mission annulée"

    date = models.DateTimeField(auto_now_add=True, db_index=True)
    moto = models.ForeignKey(
        Moto,
        on_delete=models.SET_NULL,
        related_name="alertes",
        blank=True,
        null=True,
    )
    mission = models.ForeignKey(
        Mission,
        on_delete=models.SET_NULL,
        related_name="alertes",
        blank=True,
        null=True,
    )
    type = models.CharField(max_length=30, choices=Type.choices)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["type", "is_read"]),
            models.Index(fields=["moto", "type", "is_read"]),
        ]

    def __str__(self):
        return f"{self.get_type_display()} - {self.date:%d/%m/%Y %H:%M}"
