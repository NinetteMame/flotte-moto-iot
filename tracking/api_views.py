from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import OuterRef, Subquery
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Affectation, Alert, Livreur, Mission, Moto, PositionGPS, PreuveLivraison, User
from .permissions import HasGPSAPIKey, IsLivreur, IsResponsable
from .serializers import (
    AffectationSerializer,
    AlertSerializer,
    LivreurSerializer,
    LivreurProfileSerializer,
    MissionSerializer,
    MotoSerializer,
    PositionGPSSerializer,
    PreuveLivraisonSerializer,
)
from .services import (
    alertes_pour_utilisateur,
    supprimer_livreur_et_dependances,
    supprimer_moto_et_dependances,
    traiter_nouvelle_position,
)


class LoginTokenView(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
            }
        )


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "telephone": getattr(user, "telephone", ""),
            }
        )


class RegisterManagerView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", "")).strip()
        if not username or not password:
            return Response(
                {"detail": "Nom utilisateur et mot de passe requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {"username": ["Ce nom utilisateur existe deja."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.create(
            username=username,
            first_name=request.data.get("first_name", ""),
            last_name=request.data.get("last_name", ""),
            telephone=request.data.get("telephone", ""),
            role=User.Role.RESPONSABLE,
            is_active=True,
            is_staff=True,
        )
        user.set_password(password)
        user.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "telephone": getattr(user, "telephone", ""),
            },
            status=status.HTTP_201_CREATED,
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_password = request.data.get("current_password") or request.data.get("old_password")
        new_password = request.data.get("new_password") or request.data.get("password")
        if not current_password or not new_password:
            return Response(
                {"detail": "Mot de passe actuel et nouveau mot de passe requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.check_password(current_password):
            return Response(
                {"current_password": ["Mot de passe actuel incorrect."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(new_password)
        request.user.save()
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        return Response({"detail": "Mot de passe modifie.", "token": token.key})


class ResponsableModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsResponsable]


class MotoViewSet(ResponsableModelViewSet):
    queryset = Moto.objects.prefetch_related("positions").all()
    serializer_class = MotoSerializer

    def perform_destroy(self, instance):
        supprimer_moto_et_dependances(instance)


class LivreurViewSet(ResponsableModelViewSet):
    queryset = Livreur.objects.select_related("utilisateur").all()
    serializer_class = LivreurSerializer

    def perform_destroy(self, instance):
        supprimer_livreur_et_dependances(instance)


class AffectationViewSet(ResponsableModelViewSet):
    queryset = Affectation.objects.select_related("moto", "livreur").all()
    serializer_class = AffectationSerializer


class MissionViewSet(viewsets.ModelViewSet):
    serializer_class = MissionSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "valider_otp"]:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsResponsable()]

    def get_queryset(self):
        queryset = Mission.objects.select_related("livreur", "moto")
        if self.request.user.is_responsable:
            return queryset
        return queryset.filter(livreur__utilisateur=self.request.user)

    @action(detail=True, methods=["post"], url_path="valider-otp")
    def valider_otp(self, request, pk=None):
        mission = self.get_object()
        code = str(request.data.get("otp", "")).strip()
        try:
            preuve = mission.valider_otp(code)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "detail": "Livraison validée avec succès.",
                "preuve_id": preuve.id,
                "valide_le": preuve.valide_le,
            }
        )


class PreuveViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PreuveLivraison.objects.select_related(
        "mission", "livreur", "moto"
    ).all()
    serializer_class = PreuveLivraisonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        if self.request.user.is_responsable:
            return queryset
        return queryset.filter(livreur__utilisateur=self.request.user)


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return alertes_pour_utilisateur(self.request.user)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        alerte = self.get_object()
        if not alerte.is_read:
            alerte.is_read = True
            alerte.save(update_fields=["is_read"])
        return Response(AlertSerializer(alerte).data)

    @action(detail=True, methods=["post", "delete"], url_path="delete-read")
    def delete_read(self, request, pk=None):
        alerte = self.get_object()
        if not alerte.is_read:
            return Response(
                {"detail": "L’alerte doit être lue avant sa suppression."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        alerte.is_archived = True
        alerte.save(update_fields=["is_archived"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class GPSPositionCreateView(APIView):
    authentication_classes = []
    permission_classes = [HasGPSAPIKey]

    def post(self, request):
        data = request.data.copy()
        if "moto" not in data and "moto_id" in data:
            data["moto"] = data["moto_id"]
        if "moto" not in data and data.get("moto_immatriculation"):
            immatriculation = str(data["moto_immatriculation"]).strip()
            moto = Moto.objects.filter(
                immatriculation__iexact=immatriculation
            ).first()
            if not moto:
                return Response(
                    {
                        "moto_immatriculation": [
                            f"Aucune moto trouvée avec l’immatriculation « {immatriculation} »."
                        ]
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            data["moto"] = moto.pk
        serializer = PositionGPSSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        position = serializer.save()
        traiter_nouvelle_position(position)
        return Response(
            PositionGPSSerializer(position).data, status=status.HTTP_201_CREATED
        )


class DernieresPositionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        latest_ids = (
            PositionGPS.objects.filter(moto=OuterRef("moto"))
            .order_by("-recue_le")
            .values("id")[:1]
        )
        positions = PositionGPS.objects.filter(
            id__in=Subquery(latest_ids)
        ).select_related("moto")
        if not request.user.is_responsable:
            positions = positions.filter(
                moto__affectations__livreur__utilisateur=request.user,
                moto__affectations__active=True,
            )
        return Response(PositionGPSSerializer(positions, many=True).data)


class HistoriqueGPSView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, moto_id):
        positions = PositionGPS.objects.filter(moto_id=moto_id).select_related("moto")
        if not request.user.is_responsable:
            positions = positions.filter(
                moto__affectations__livreur__utilisateur=request.user,
                moto__affectations__active=True,
            )
        limit = min(int(request.query_params.get("limit", 200)), 1000)
        return Response(PositionGPSSerializer(positions[:limit], many=True).data)


class LivreurProfileAPIView(APIView):
    permission_classes = [IsAuthenticated, IsLivreur]

    def get(self, request):
        return Response(LivreurProfileSerializer(request.user.profil_livreur).data)

class LivreurMissionsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsLivreur]

    def get(self, request):
        missions = Mission.objects.filter(
            livreur__utilisateur=request.user
        ).select_related("livreur", "moto")
        return Response(
            MissionSerializer(missions, many=True, context={"request": request}).data
        )


class LivreurHistoriqueAPIView(APIView):
    permission_classes = [IsAuthenticated, IsLivreur]

    def get(self, request):
        missions = Mission.objects.filter(
            livreur__utilisateur=request.user,
            statut=Mission.Statut.TERMINEE,
        ).select_related("livreur", "moto")
        return Response(
            MissionSerializer(missions, many=True, context={"request": request}).data
        )
