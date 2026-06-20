from django.core.management.base import BaseCommand

from tracking.services import verifier_alertes_gps


class Command(BaseCommand):
    help = "Crée les alertes pour les motos dont le GPS ne répond plus."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=None,
            help="Délai sans position avant alerte (10 minutes par défaut).",
        )

    def handle(self, *args, **options):
        alertes = verifier_alertes_gps(options["minutes"])
        self.stdout.write(
            self.style.SUCCESS(f"{len(alertes)} nouvelle(s) alerte(s) GPS créée(s).")
        )
