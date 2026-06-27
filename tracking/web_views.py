from datetime import timedelta
from functools import wraps
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    AffectationForm,
    LivreurCreateForm,
    LivreurPasswordResetForm,
    LivreurUpdateForm,
    MissionForm,
    MotoForm,
    OTPForm,
    ResponsablePasswordChangeForm,
    ResponsableProfileForm,
    ResponsableRegistrationForm,
)
from .models import (
    Affectation,
    Alert,
    Livreur,
    Mission,
    Moto,
    PositionGPS,
    PreuveLivraison,
)
from .services import (
    alertes_pour_utilisateur,
    resume_suppression_livreur,
    resume_suppression_moto,
    supprimer_livreur_et_dependances,
    supprimer_moto_et_dependances,
    verifier_alertes_gps,
)


class MotoTrackLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.is_responsable:
            return redirect("dashboard").url
        return redirect("livreur-dashboard").url


def responsable_register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = ResponsableRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Votre compte responsable a été créé. Vous pouvez vous connecter.",
        )
        return redirect("login")
    return render(request, "registration/register.html", {"form": form})


def responsable_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_responsable:
            return HttpResponseForbidden("Accès réservé au responsable.")
        return view_func(request, *args, **kwargs)

    return wrapped


def livreur_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if request.user.is_responsable or not hasattr(
            request.user, "profil_livreur"
        ):
            return HttpResponseForbidden("Accès réservé aux livreurs.")
        return view_func(request, *args, **kwargs)

    return wrapped


@login_required
def home(request):
    if request.user.is_responsable:
        return redirect("dashboard")
    return redirect("livreur-dashboard")


@responsable_required
def dashboard(request):
    latest_ids = (
        PositionGPS.objects.filter(moto=OuterRef("moto"))
        .order_by("-recue_le")
        .values("id")[:1]
    )
    context = {
        "total_motos": Moto.objects.count(),
        "total_livreurs": Livreur.objects.filter(actif=True).count(),
        "livreurs_inactifs": Livreur.objects.filter(actif=False).count(),
        "missions_en_cours": Mission.objects.filter(
            statut=Mission.Statut.EN_COURS
        ).count(),
        "missions_terminees": Mission.objects.filter(
            statut=Mission.Statut.TERMINEE
        ).count(),
        "missions_annulees": Mission.objects.filter(
            statut=Mission.Statut.ANNULEE
        ).count(),
        "missions_en_attente": Mission.objects.filter(
            statut=Mission.Statut.EN_ATTENTE
        ).count(),
        "dernieres_positions": PositionGPS.objects.filter(
            id__in=Subquery(latest_ids)
        ).select_related("moto")[:6],
        "missions_recentes": Mission.objects.select_related("livreur", "moto")[:6],
    }
    return render(request, "tracking/dashboard.html", context)


@responsable_required
def moto_list(request):
    return render(
        request,
        "tracking/moto_list.html",
        {"motos": Moto.objects.all()},
    )


@responsable_required
def moto_form(request, pk=None):
    moto = get_object_or_404(Moto, pk=pk) if pk else None
    form = MotoForm(request.POST or None, instance=moto)
    if form.is_valid():
        form.save()
        messages.success(request, "Moto enregistrée avec succès.")
        return redirect("moto-list")
    return render(
        request,
        "tracking/form.html",
        {"form": form, "titre": "Modifier la moto" if moto else "Ajouter une moto"},
    )


@responsable_required
def moto_delete(request, pk):
    moto = get_object_or_404(Moto, pk=pk)
    if request.method == "POST":
        immatriculation = moto.immatriculation
        supprimer_moto_et_dependances(moto)
        messages.success(
            request,
            f"La moto {immatriculation} et ses données associées ont été supprimées.",
        )
        return redirect("moto-list")
    return render(
        request,
        "tracking/confirm_delete.html",
        {
            "objet": moto,
            "type_objet": "la moto",
            "dependances": resume_suppression_moto(moto),
        },
    )


@responsable_required
def livreur_list(request):
    return render(
        request,
        "tracking/livreur_list.html",
        {"livreurs": Livreur.objects.select_related("utilisateur")},
    )


@responsable_required
def livreur_detail(request, pk):
    livreur = get_object_or_404(
        Livreur.objects.select_related("utilisateur").prefetch_related(
            "affectations__moto", "missions"
        ),
        pk=pk,
    )
    affectation = livreur.affectations.filter(active=True).select_related("moto").first()
    context = {
        "livreur": livreur,
        "affectation": affectation,
        "missions_total": livreur.missions.count(),
        "missions_terminees": livreur.missions.filter(
            statut=Mission.Statut.TERMINEE
        ).count(),
    }
    return render(request, "tracking/livreur_detail.html", context)


@login_required
def livreur_contrat_download(request, pk):
    livreur = get_object_or_404(Livreur, pk=pk)
    est_proprietaire = (
        hasattr(request.user, "profil_livreur")
        and request.user.profil_livreur.pk == livreur.pk
    )
    if not request.user.is_responsable and not est_proprietaire:
        return HttpResponseForbidden("Accès interdit à ce contrat.")
    if not livreur.document_contrat:
        raise Http404("Aucun contrat n'est disponible.")
    return FileResponse(
        livreur.document_contrat.open("rb"),
        as_attachment=True,
        filename=Path(livreur.document_contrat.name).name,
    )


@responsable_required
def livreur_create(request):
    form = LivreurCreateForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Compte livreur créé avec succès.")
        return redirect("livreur-list")
    return render(
        request, "tracking/form.html", {"form": form, "titre": "Ajouter un livreur"}
    )


@responsable_required
def livreur_update(request, pk):
    livreur = get_object_or_404(Livreur, pk=pk)
    form = LivreurUpdateForm(
        request.POST or None, request.FILES or None, instance=livreur
    )
    if form.is_valid():
        form.save()
        messages.success(request, "Livreur mis à jour.")
        return redirect("livreur-list")
    return render(
        request, "tracking/form.html", {"form": form, "titre": "Modifier le livreur"}
    )


@responsable_required
def livreur_password_reset(request, pk):
    livreur = get_object_or_404(Livreur.objects.select_related("utilisateur"), pk=pk)
    form = LivreurPasswordResetForm(livreur.utilisateur, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            f"Le mot de passe de {livreur} a été remplacé avec succès.",
        )
        return redirect("livreur-detail", pk=livreur.pk)
    return render(
        request,
        "tracking/form.html",
        {
            "form": form,
            "titre": f"Nouveau mot de passe pour {livreur}",
        },
    )


@responsable_required
def livreur_delete(request, pk):
    livreur = get_object_or_404(Livreur, pk=pk)
    if request.method == "POST":
        nom_livreur = str(livreur)
        supprimer_livreur_et_dependances(livreur)
        messages.success(
            request,
            f"Le livreur {nom_livreur}, son compte et ses données associées ont été supprimés.",
        )
        return redirect("livreur-list")
    return render(
        request,
        "tracking/confirm_delete.html",
        {
            "objet": livreur,
            "type_objet": "le livreur",
            "dependances": resume_suppression_livreur(livreur),
        },
    )


@responsable_required
def affectation_list(request):
    return render(
        request,
        "tracking/affectation_list.html",
        {"affectations": Affectation.objects.select_related("moto", "livreur")},
    )


@responsable_required
def affectation_form(request, pk=None):
    affectation = get_object_or_404(Affectation, pk=pk) if pk else None
    form = AffectationForm(request.POST or None, instance=affectation)
    if form.is_valid():
        form.save()
        messages.success(request, "Affectation enregistrée.")
        return redirect("affectation-list")
    return render(
        request,
        "tracking/form.html",
        {
            "form": form,
            "titre": "Modifier l’affectation" if affectation else "Nouvelle affectation",
        },
    )


@responsable_required
def affectation_delete(request, pk):
    affectation = get_object_or_404(Affectation, pk=pk)
    if request.method == "POST":
        affectation.delete()
        messages.success(request, "Affectation supprimée.")
        return redirect("affectation-list")
    return render(request, "tracking/confirm_delete.html", {"objet": affectation})


@responsable_required
def mission_list(request):
    return render(
        request,
        "tracking/mission_list.html",
        {"missions": Mission.objects.select_related("livreur", "moto")},
    )


@responsable_required
def mission_form(request, pk=None):
    mission = get_object_or_404(Mission, pk=pk) if pk else None
    form = MissionForm(request.POST or None, instance=mission)
    if form.is_valid():
        mission = form.save()
        messages.success(
            request, f"Mission enregistrée. OTP client : {mission.otp}"
        )
        return redirect("mission-detail", pk=mission.pk)
    return render(
        request,
        "tracking/mission_form.html",
        {"form": form, "titre": "Modifier la mission" if mission else "Créer une mission"},
    )


@login_required
def mission_detail(request, pk):
    mission = get_object_or_404(
        Mission.objects.select_related("livreur", "moto"), pk=pk
    )
    if not request.user.is_responsable and mission.livreur.utilisateur != request.user:
        return HttpResponseForbidden("Cette mission ne vous est pas affectée.")
    return render(request, "tracking/mission_detail.html", {"mission": mission})


@responsable_required
def mission_delete(request, pk):
    mission = get_object_or_404(Mission, pk=pk)
    if request.method == "POST":
        mission.delete()
        messages.success(request, "Mission supprimée.")
        return redirect("mission-list")
    return render(request, "tracking/confirm_delete.html", {"objet": mission})


@responsable_required
def gps_map(request):
    motos_suivies = Moto.objects.filter(positions__isnull=False).distinct()
    motos_sans_positions = Moto.objects.filter(positions__isnull=True)
    return render(
        request,
        "tracking/gps_map.html",
        {
            "motos_suivies": motos_suivies,
            "motos_sans_positions": motos_sans_positions,
            "google_maps_enabled": False,
        },
    )


@responsable_required
def preuve_list(request):
    preuves = PreuveLivraison.objects.select_related("mission", "livreur", "moto")
    return render(request, "tracking/preuve_list.html", {"preuves": preuves})


@login_required
def alert_list(request):
    alertes = alertes_pour_utilisateur(request.user)
    return render(request, "tracking/alert_list.html", {"alertes": alertes})


@login_required
def alert_mark_read(request, pk):
    alerte = get_object_or_404(alertes_pour_utilisateur(request.user), pk=pk)
    if request.method == "POST" and not alerte.is_read:
        alerte.is_read = True
        alerte.save(update_fields=["is_read"])
        messages.success(request, "L’alerte a été marquée comme lue.")
    return redirect("alert-list")


@login_required
def alert_delete(request, pk):
    alerte = get_object_or_404(alertes_pour_utilisateur(request.user), pk=pk)
    if request.method != "POST":
        return HttpResponseForbidden("Méthode non autorisée.")
    if not alerte.is_read:
        messages.error(
            request,
            "Une alerte doit être marquée comme lue avant sa suppression.",
        )
        return redirect("alert-list")
    alerte.is_archived = True
    alerte.save(update_fields=["is_archived"])
    messages.success(request, "L’alerte a été supprimée.")
    return redirect("alert-list")


@responsable_required
def alert_check_gps(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Méthode non autorisée."}, status=405)

    nouvelles_alertes = verifier_alertes_gps()
    alertes = alertes_pour_utilisateur(request.user)
    return JsonResponse(
        {
            "unread_count": alertes.filter(is_read=False).count(),
            "created": [
                {
                    "id": alerte.id,
                    "type": alerte.get_type_display(),
                    "message": alerte.message,
                }
                for alerte in nouvelles_alertes
            ],
        }
    )


@responsable_required
def responsable_profile(request):
    action = request.POST.get("action") if request.method == "POST" else None
    profile_form = ResponsableProfileForm(
        request.POST if action == "profile" else None,
        instance=request.user,
        prefix="profile",
    )
    password_form = ResponsablePasswordChangeForm(
        request.user,
        request.POST if action == "password" else None,
        prefix="password",
    )

    if request.method == "POST":
        if action == "profile" and profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Votre profil a été mis à jour.")
            return redirect("responsable-profile")
        if action == "password" and password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Votre mot de passe a été modifié.")
            return redirect("responsable-profile")

    return render(
        request,
        "tracking/responsable_profile.html",
        {"profile_form": profile_form, "password_form": password_form},
    )


@livreur_required
def livreur_missions(request):
    missions = Mission.objects.filter(
        livreur__utilisateur=request.user
    ).select_related("moto")
    return render(request, "tracking/livreur_missions.html", {"missions": missions})


@livreur_required
def livreur_dashboard(request):
    livreur = request.user.profil_livreur
    missions = livreur.missions.select_related("moto")
    affectation = livreur.affectations.filter(active=True).select_related("moto").first()
    moto = affectation.moto if affectation else None
    derniere_position = moto.positions.first() if moto else None
    context = {
        "livreur": livreur,
        "moto": moto,
        "derniere_position": derniere_position,
        "missions_recentes": missions[:4],
        "missions_en_attente": missions.filter(
            statut=Mission.Statut.EN_ATTENTE
        ).count(),
        "missions_en_cours": missions.filter(statut=Mission.Statut.EN_COURS).count(),
        "missions_terminees": missions.filter(
            statut=Mission.Statut.TERMINEE
        ).count(),
        "missions_annulees": missions.filter(
            statut=Mission.Statut.ANNULEE
        ).count(),
        "total_livraisons": missions.filter(
            statut=Mission.Statut.TERMINEE
        ).count(),
    }
    return render(request, "tracking/livreur_dashboard.html", context)


@livreur_required
def livreur_profile(request):
    livreur = request.user.profil_livreur
    if request.method == "POST":
        return HttpResponseForbidden(
            "Le profil du livreur est consultable uniquement."
        )
    return render(
        request,
        "tracking/livreur_profile.html",
        {"livreur": livreur},
    )


@livreur_required
def livreur_moto(request):
    affectation = (
        request.user.profil_livreur.affectations.filter(active=True)
        .select_related("moto")
        .first()
    )
    moto = affectation.moto if affectation else None
    return render(
        request,
        "tracking/livreur_moto.html",
        {
            "affectation": affectation,
            "moto": moto,
            "derniere_position": moto.positions.first() if moto else None,
        },
    )


@livreur_required
def livreur_livraisons(request):
    missions = request.user.profil_livreur.missions.filter(
        statut=Mission.Statut.TERMINEE
    ).select_related("moto")
    periode = request.GET.get("periode", "")
    maintenant = timezone.localtime()
    if periode == "today":
        missions = missions.filter(otp_valide_le__date=maintenant.date())
    elif periode == "week":
        missions = missions.filter(
            otp_valide_le__date__gte=maintenant.date() - timedelta(days=6)
        )
    elif periode == "month":
        missions = missions.filter(
            otp_valide_le__year=maintenant.year,
            otp_valide_le__month=maintenant.month,
        )
    recherche = request.GET.get("q", "").strip()
    if recherche:
        missions = missions.filter(nom_client__icontains=recherche)
    return render(
        request,
        "tracking/livreur_livraisons.html",
        {"missions": missions, "periode": periode, "recherche": recherche},
    )


@livreur_required
def preuve_livraison_detail(request, pk):
    preuve = get_object_or_404(
        PreuveLivraison.objects.select_related("mission", "livreur", "moto"),
        pk=pk,
        livreur__utilisateur=request.user,
    )
    return render(request, "tracking/livreur_preuve.html", {"preuve": preuve})


@livreur_required
def preuve_livraison_pdf(request, pk):
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    preuve = get_object_or_404(
        PreuveLivraison.objects.select_related("mission", "livreur", "moto"),
        pk=pk,
        livreur__utilisateur=request.user,
    )
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Preuve livraison mission {preuve.mission_id}")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(70, 780, "MOTOTRACK")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(70, 752, "MOTOTRACK - Preuve officielle de livraison")
    pdf.line(70, 735, 525, 735)
    lignes = [
        ("Mission", f"#{preuve.mission_id}"),
        ("Client", preuve.client),
        ("Adresse", preuve.mission.adresse_livraison),
        ("Livreur", str(preuve.livreur)),
        ("Moto", preuve.moto.immatriculation),
        ("OTP validé", preuve.otp_valide),
        ("Date", timezone.localtime(preuve.valide_le).strftime("%d/%m/%Y")),
        ("Heure", timezone.localtime(preuve.valide_le).strftime("%H:%M:%S")),
    ]
    y = 695
    for libelle, valeur in lignes:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(70, y, f"{libelle} :")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(180, y, str(valeur))
        y -= 34
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(70, 80, "Document généré automatiquement par MotoTrack.")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"preuve-mission-{preuve.mission_id}.pdf",
        content_type="application/pdf",
    )


@login_required
def valider_otp(request, pk):
    mission = get_object_or_404(Mission, pk=pk)
    if not request.user.is_responsable and mission.livreur.utilisateur != request.user:
        return HttpResponseForbidden("Cette mission ne vous est pas affectée.")
    form = OTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            mission.valider_otp(form.cleaned_data["otp"])
        except ValidationError as exc:
            form.add_error("otp", exc.messages[0])
        else:
            messages.success(request, "Livraison validée. La preuve a été enregistrée.")
            return redirect("mission-detail", pk=mission.pk)
    return render(
        request,
        "tracking/form.html",
        {"form": form, "titre": f"Valider la mission #{mission.pk}"},
    )
