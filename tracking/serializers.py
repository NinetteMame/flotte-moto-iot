from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

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


class MotoSerializer(serializers.ModelSerializer):
    derniere_position = serializers.SerializerMethodField()

    class Meta:
        model = Moto
        fields = [
            "id",
            "immatriculation",
            "marque",
            "modele",
            "etat",
            "derniere_position",
        ]

    def get_derniere_position(self, obj):
        position = obj.positions.first()
        return PositionGPSSerializer(position).data if position else None


class LivreurSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="utilisateur.username", required=False)
    email = serializers.EmailField(source="utilisateur.email", required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    new_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Livreur
        fields = [
            "id",
            "utilisateur",
            "username",
            "email",
            "password",
            "new_password",
            "nom",
            "prenom",
            "age",
            "telephone",
            "adresse",
            "numero_permis",
            "numero_cni",
            "photo",
            "type_contrat",
            "date_debut_contrat",
            "date_fin_contrat",
            "document_contrat",
            "actif",
        ]
        extra_kwargs = {"utilisateur": {"required": False}}

    def create(self, validated_data):
        user_data = validated_data.pop("utilisateur", {})
        password = validated_data.pop("password", "")
        validated_data.pop("new_password", None)
        username = user_data.get("username") or validated_data.get("telephone") or f"livreur{User.objects.count() + 1}"
        user = User(
            username=username,
            email=user_data.get("email", ""),
            first_name=validated_data.get("prenom", ""),
            last_name=validated_data.get("nom", ""),
            role=User.Role.LIVREUR,
            is_active=True,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return Livreur.objects.create(utilisateur=user, **validated_data)

    def update(self, instance, validated_data):
        user_data = validated_data.pop("utilisateur", {})
        password = validated_data.pop("password", "")
        new_password = validated_data.pop("new_password", "")
        user = instance.utilisateur
        if "username" in user_data and user_data["username"]:
            user.username = user_data["username"]
        if "email" in user_data:
            user.email = user_data["email"]
        user.first_name = validated_data.get("prenom", instance.prenom)
        user.last_name = validated_data.get("nom", instance.nom)
        if password:
            user.set_password(password)
        if new_password:
            user.set_password(new_password)
        user.is_active = validated_data.get("actif", instance.actif)
        user.role = User.Role.LIVREUR
        user.save()
        return super().update(instance, validated_data)


class LivreurProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="utilisateur.email", read_only=True)
    username = serializers.CharField(source="utilisateur.username", read_only=True)

    class Meta:
        model = Livreur
        fields = [
            "id",
            "username",
            "email",
            "nom",
            "prenom",
            "age",
            "telephone",
            "adresse",
            "numero_permis",
            "numero_cni",
            "photo",
            "type_contrat",
            "date_debut_contrat",
            "date_fin_contrat",
            "document_contrat",
            "actif",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "nom",
            "prenom",
            "numero_permis",
            "numero_cni",
            "type_contrat",
            "date_debut_contrat",
            "date_fin_contrat",
            "document_contrat",
            "actif",
        ]


class AffectationSerializer(serializers.ModelSerializer):
    moto_detail = MotoSerializer(source="moto", read_only=True)
    livreur_nom = serializers.CharField(source="livreur.__str__", read_only=True)

    class Meta:
        model = Affectation
        fields = [
            "id",
            "moto",
            "moto_detail",
            "livreur",
            "livreur_nom",
            "date_debut",
            "date_fin",
            "active",
            "notes",
        ]

    def validate(self, attrs):
        instance = self.instance or Affectation()
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            ) from exc
        return attrs


class MissionSerializer(serializers.ModelSerializer):
    client_nom = serializers.CharField(source="nom_client", read_only=True)
    livreur_nom = serializers.CharField(source="livreur.__str__", read_only=True)
    moto_immatriculation = serializers.CharField(
        source="moto.immatriculation", read_only=True
    )
    moto_detail = serializers.SerializerMethodField()
    last_position = serializers.SerializerMethodField()
    otp = serializers.SerializerMethodField()

    class Meta:
        model = Mission
        fields = [
            "id",
            "client_nom",
            "nom_client",
            "telephone_client",
            "adresse_livraison",
            "description_lieu",
            "destination_latitude",
            "destination_longitude",
            "livreur",
            "livreur_nom",
            "moto",
            "moto_immatriculation",
            "moto_detail",
            "last_position",
            "statut",
            "otp",
            "otp_valide_le",
            "cree_le",
            "modifie_le",
        ]
        read_only_fields = ["otp_valide_le", "cree_le", "modifie_le"]

    def get_otp(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.is_responsable:
            return obj.otp
        return None

    def get_moto_detail(self, obj):
        return {
            "id": obj.moto_id,
            "immatriculation": obj.moto.immatriculation,
        }

    def get_last_position(self, obj):
        position = obj.moto.positions.first()
        if not position:
            return None
        return {
            "latitude": position.latitude,
            "longitude": position.longitude,
            "date": position.recue_le,
        }

    def validate(self, attrs):
        instance = self.instance or Mission()
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return attrs


class PositionGPSSerializer(serializers.ModelSerializer):
    moto_immatriculation = serializers.CharField(
        source="moto.immatriculation", read_only=True
    )

    class Meta:
        model = PositionGPS
        fields = [
            "id",
            "moto",
            "moto_immatriculation",
            "latitude",
            "longitude",
            "date_appareil",
            "heure_appareil",
            "recue_le",
        ]
        read_only_fields = ["recue_le"]

    def validate_latitude(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude invalide.")
        return value

    def validate_longitude(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude invalide.")
        return value


class PreuveLivraisonSerializer(serializers.ModelSerializer):
    livreur_nom = serializers.CharField(source="livreur.__str__", read_only=True)
    moto_immatriculation = serializers.CharField(
        source="moto.immatriculation", read_only=True
    )

    class Meta:
        model = PreuveLivraison
        fields = [
            "id",
            "mission",
            "livreur",
            "livreur_nom",
            "moto",
            "moto_immatriculation",
            "client",
            "valide_le",
            "otp_valide",
        ]


class AlertSerializer(serializers.ModelSerializer):
    moto_immatriculation = serializers.CharField(
        source="moto.immatriculation", read_only=True
    )
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id",
            "date",
            "moto",
            "moto_immatriculation",
            "mission",
            "type",
            "type_display",
            "message",
            "is_read",
            "is_archived",
        ]
        read_only_fields = fields
