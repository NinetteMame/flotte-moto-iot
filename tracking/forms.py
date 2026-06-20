from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm, UserCreationForm
from django.db import transaction

from .models import Affectation, Livreur, Mission, Moto, User


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            current = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{current} form-control".strip()


class MotoForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Moto
        fields = ["immatriculation", "marque", "modele", "etat"]


class AffectationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Affectation
        fields = ["moto", "livreur", "date_debut", "date_fin", "active", "notes"]
        labels = {"active": "Affectation active"}
        widgets = {
            "date_debut": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "date_fin": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class MissionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Mission
        fields = [
            "nom_client",
            "telephone_client",
            "adresse_livraison",
            "description_lieu",
            "destination_latitude",
            "destination_longitude",
            "livreur",
            "moto",
            "statut",
        ]
        labels = {
            "destination_latitude": "Latitude de destination",
            "destination_longitude": "Longitude de destination",
        }
        widgets = {
            "destination_latitude": forms.NumberInput(
                attrs={"step": "0.0000001", "placeholder": "Ex. 14.6928000"}
            ),
            "destination_longitude": forms.NumberInput(
                attrs={"step": "0.0000001", "placeholder": "Ex. -16.4665000"}
            ),
        }


class LivreurCreateForm(StyledFormMixin, UserCreationForm):
    nom = forms.CharField(max_length=80)
    prenom = forms.CharField(max_length=80)
    age = forms.IntegerField(min_value=18, max_value=80, label="Âge")
    telephone = forms.CharField(max_length=30)
    adresse = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    numero_permis = forms.CharField(max_length=60)
    numero_cni = forms.CharField(max_length=60)
    photo = forms.ImageField(required=False)
    type_contrat = forms.ChoiceField(
        choices=Livreur.TypeContrat.choices,
        label="Type de contrat",
    )
    date_debut_contrat = forms.DateField(
        required=False,
        label="Date de début du contrat",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_fin_contrat = forms.DateField(
        required=False,
        label="Date de fin du contrat",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    document_contrat = forms.FileField(
        required=False,
        label="Document du contrat",
        help_text="Formats conseillés : PDF, DOC ou DOCX.",
    )
    actif = forms.BooleanField(required=False, initial=True, label="Livreur actif")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean(self):
        cleaned_data = super().clean()
        type_contrat = cleaned_data.get("type_contrat")
        date_debut = cleaned_data.get("date_debut_contrat")
        date_fin = cleaned_data.get("date_fin_contrat")
        if type_contrat == Livreur.TypeContrat.CDD:
            if not date_debut:
                self.add_error(
                    "date_debut_contrat",
                    "La date de début est obligatoire pour un CDD.",
                )
            if not date_fin:
                self.add_error(
                    "date_fin_contrat",
                    "La date de fin est obligatoire pour un CDD.",
                )
            if date_debut and date_fin and date_fin < date_debut:
                self.add_error(
                    "date_fin_contrat",
                    "La date de fin doit suivre la date de début.",
                )
        elif date_fin:
            self.add_error(
                "date_fin_contrat",
                "Un contrat CDI ne possède pas de date de fin.",
            )
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["prenom"]
        user.last_name = self.cleaned_data["nom"]
        user.role = User.Role.LIVREUR
        if commit:
            user.save()
            Livreur.objects.create(
                utilisateur=user,
                nom=self.cleaned_data["nom"],
                prenom=self.cleaned_data["prenom"],
                age=self.cleaned_data["age"],
                telephone=self.cleaned_data["telephone"],
                adresse=self.cleaned_data["adresse"],
                numero_permis=self.cleaned_data["numero_permis"],
                numero_cni=self.cleaned_data["numero_cni"],
                photo=self.cleaned_data.get("photo"),
                type_contrat=self.cleaned_data["type_contrat"],
                date_debut_contrat=self.cleaned_data.get("date_debut_contrat"),
                date_fin_contrat=self.cleaned_data.get("date_fin_contrat"),
                document_contrat=self.cleaned_data.get("document_contrat"),
                actif=self.cleaned_data["actif"],
            )
        return user


class LivreurUpdateForm(StyledFormMixin, forms.ModelForm):
    email = forms.EmailField(required=False)
    age = forms.IntegerField(min_value=18, max_value=80, label="Âge")

    class Meta:
        model = Livreur
        fields = [
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
        widgets = {
            "date_debut_contrat": forms.DateInput(attrs={"type": "date"}),
            "date_fin_contrat": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["email"].initial = self.instance.utilisateur.email

    def clean(self):
        cleaned_data = super().clean()
        type_contrat = cleaned_data.get("type_contrat")
        date_debut = cleaned_data.get("date_debut_contrat")
        date_fin = cleaned_data.get("date_fin_contrat")
        if type_contrat == Livreur.TypeContrat.CDD:
            if not date_debut:
                self.add_error("date_debut_contrat", "Requis pour un CDD.")
            if not date_fin:
                self.add_error("date_fin_contrat", "Requis pour un CDD.")
            if date_debut and date_fin and date_fin < date_debut:
                self.add_error(
                    "date_fin_contrat",
                    "La date de fin doit suivre la date de début.",
                )
        elif date_fin:
            self.add_error(
                "date_fin_contrat",
                "Un contrat CDI ne possède pas de date de fin.",
            )
        return cleaned_data

    def save(self, commit=True):
        livreur = super().save(commit)
        if commit:
            user = livreur.utilisateur
            user.first_name = livreur.prenom
            user.last_name = livreur.nom
            user.email = self.cleaned_data["email"]
            user.save(update_fields=["first_name", "last_name", "email"])
        return livreur


class OTPForm(StyledFormMixin, forms.Form):
    otp = forms.CharField(
        min_length=6,
        max_length=6,
        label="Code OTP du client",
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "placeholder": "000000",
            }
        ),
    )


class ResponsableProfileForm(StyledFormMixin, forms.ModelForm):
    email = forms.EmailField(label="Adresse e-mail")
    telephone = forms.CharField(max_length=30, label="Numéro de téléphone")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "telephone"]
        labels = {
            "username": "Nom d'utilisateur",
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Adresse e-mail",
            "telephone": "Numéro de téléphone",
        }


class ResponsablePasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


class ResponsableRegistrationForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(label="Adresse e-mail")
    telephone = forms.CharField(max_length=30, label="Numéro de téléphone")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "password1",
            "password2",
        ]
        labels = {
            "username": "Nom d'utilisateur",
            "first_name": "Prénom",
            "last_name": "Nom",
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.RESPONSABLE
        if commit:
            user.save()
        return user


class LivreurPasswordResetForm(StyledFormMixin, SetPasswordForm):
    pass


class LivreurProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Livreur
        fields = ["telephone", "adresse", "photo"]
        labels = {
            "telephone": "Numéro de téléphone",
            "adresse": "Adresse",
            "photo": "Photo de profil",
        }
        widgets = {"adresse": forms.Textarea(attrs={"rows": 3})}


class LivreurPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass
