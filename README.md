# MotoTrack

MotoTrack est une plateforme web IoT de gestion et de suivi de motos de
livraison. Elle associe Django, Django REST Framework, PostgreSQL, Leaflet et
un ESP32 équipé d'un GPS NEO-6M.

Le projet est volontairement structuré de façon simple pour être compris,
démontré et expliqué dans le cadre d'une soutenance de Licence.

## Fonctionnalités

- Deux rôles : responsable et livreur.
- Gestion des motos, livreurs, affectations et missions.
- Blocage des doubles affectations actives.
- OTP à six chiffres créé automatiquement pour chaque mission.
- Validation de livraison et création d'une preuve horodatée.
- Réception et conservation de toutes les positions GPS.
- Carte Leaflet avec rafraîchissement automatique.
- API REST authentifiée par token pour les données métier.
- API GPS protégée par l'en-tête `X-API-Key`.
- Interface responsive pour ordinateur, tablette et téléphone.
- Configuration PostgreSQL locale, Supabase et Render.

## Structure

```text
MotoTrack/
├── arduino/
│   └── mototrack_esp32_gps.ino
├── mototrack/                 # Configuration Django
├── tracking/                  # Application métier et API
│   ├── management/commands/   # Commande de données de démonstration
│   ├── migrations/
│   ├── models.py
│   ├── serializers.py
│   ├── api_views.py
│   ├── web_views.py
│   ├── forms.py
│   └── tests.py
├── templates/                 # Pages HTML
├── static/                    # CSS et JavaScript
├── .env.example
├── render.yaml
├── Procfile
├── build.sh
├── requirements.txt
└── manage.py
```

## 1. Installation locale

### Prérequis

- Python 3.11 ou plus récent
- PostgreSQL 14 ou plus récent
- Git, facultatif
- Un ordinateur, l'ESP32 et les appareils de test sur le même Wi-Fi

Dans PowerShell, depuis le dossier du projet :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Ne publiez jamais le fichier `.env`. Il contient les secrets.

## 2. PostgreSQL local

Ouvrez `psql` avec le compte administrateur PostgreSQL :

```sql
CREATE USER mototrack_user WITH PASSWORD 'mot_de_passe_local';
CREATE DATABASE mototrack OWNER mototrack_user;
GRANT ALL PRIVILEGES ON DATABASE mototrack TO mototrack_user;
```

Renseignez ensuite la partie locale de `.env` :

```env
DB_ENGINE=postgresql
DB_NAME=mototrack
DB_USER=mototrack_user
DB_PASSWORD=mot_de_passe_local
DB_HOST=localhost
DB_PORT=5432
DB_SSL_REQUIRE=False
```

Créez les tables et le compte administrateur :

```powershell
python manage.py migrate
python manage.py createsuperuser
```

Pour charger un responsable, un livreur, une moto, une mission et des
positions GPS de démonstration :

```powershell
python manage.py creer_demo
```

Comptes de démonstration :

- Responsable : `responsable` / `MotoTrack2026!`
- Livreur : `livreur` / `MotoTrack2026!`

Changez ces mots de passe avant toute utilisation réelle.

## 3. Lancement local

Pour un accès limité à l'ordinateur :

```powershell
python manage.py runserver
```

Pour rendre le serveur accessible à l'ESP32 et aux téléphones du même réseau :

```powershell
python manage.py runserver 0.0.0.0:8000
```

Ouvrez ensuite `http://127.0.0.1:8000` sur l'ordinateur.

## 4. Trouver l'adresse IP locale du PC

Sous Windows :

```powershell
ipconfig
```

Repérez l'adresse **IPv4** de la carte Wi-Fi, par exemple `192.168.1.10`.
Ajoutez-la dans `.env` :

```env
ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.10
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://192.168.1.10:8000
```

Redémarrez Django après toute modification de `.env`. Depuis un téléphone
connecté au même Wi-Fi, ouvrez `http://192.168.1.10:8000`.

Si la page ne répond pas, autorisez Python ou le port TCP 8000 dans le
pare-feu Windows pour les réseaux privés.

## 5. Tester l'API GPS avec Postman

Créez d'abord une moto dans MotoTrack et notez son identifiant numérique.

- Méthode : `POST`
- URL locale : `http://192.168.1.10:8000/api/gps/positions/`
- Header : `Content-Type: application/json`
- Header : `X-API-Key: mototrack-gps-cle-a-modifier`
- Body JSON :

```json
{
  "moto": 1,
  "latitude": 0.3365400,
  "longitude": 6.7273200,
  "date_appareil": "2026-06-13",
  "heure_appareil": "12:30:00"
}
```

Une réponse `201 Created` confirme l'enregistrement. La position apparaît
dans **Carte GPS** au prochain rafraîchissement.

## 6. Tester avec l'ESP32 et le NEO-6M

1. Ouvrez `arduino/mototrack_esp32_gps.ino` dans l'IDE Arduino.
2. Installez la carte ESP32 et la bibliothèque `TinyGPSPlus`.
3. Branchez le GPS comme indiqué dans les commentaires du fichier.
4. Modifiez `WIFI_SSID`, `WIFI_PASSWORD`, `API_URL`, `GPS_API_KEY` et `MOTO_ID`.
5. Utilisez l'IP du PC, jamais `127.0.0.1`, dans l'URL locale.
6. Téléversez le programme et ouvrez le moniteur série à 115200 bauds.
7. Placez le GPS dehors ou près d'une fenêtre pour obtenir un signal satellite.

L'ordinateur serveur, l'ESP32 et le téléphone de test doivent être connectés
au même réseau Wi-Fi. Certains réseaux invités bloquent la communication entre
appareils ; utilisez alors un routeur normal ou le partage de connexion d'un
téléphone.

## 7. API REST

Authentification par token :

```http
POST /api/auth/token/
Content-Type: application/json

{"username": "responsable", "password": "votre-mot-de-passe"}
```

Utilisez ensuite :

```http
Authorization: Token VOTRE_TOKEN
```

Principales routes :

| Méthode | Route | Usage |
|---|---|---|
| POST | `/api/auth/token/` | Obtenir un token |
| CRUD | `/api/motos/` | Gérer les motos |
| CRUD | `/api/livreurs/` | Gérer les livreurs |
| CRUD | `/api/affectations/` | Gérer les affectations |
| CRUD | `/api/missions/` | Gérer les missions |
| POST | `/api/missions/{id}/valider-otp/` | Valider une livraison |
| GET | `/api/preuves/` | Consulter les preuves |
| POST | `/api/gps/positions/` | Envoyer une position ESP32 |
| GET | `/api/gps/dernieres-positions/` | Dernière position de chaque moto |
| GET | `/api/gps/motos/{id}/historique/` | Historique d'une moto |
| GET | `/api/alerts/` | Lister les alertes accessibles |
| GET | `/api/alerts/unread-count/` | Compter les alertes non lues |
| POST | `/api/alerts/{id}/mark-read/` | Marquer une alerte comme lue |

## Alertes automatiques

MotoTrack crée des alertes lorsqu'une moto sort du Sénégal, lorsqu'une mission
est validée par OTP ou lorsqu'une moto affectée n'envoie plus de position GPS.

La vérification des GPS silencieux peut être lancée manuellement :

```powershell
python manage.py check_gps_alerts
```

Le délai par défaut est de 10 minutes. Il peut être modifié dans `.env` :

```env
GPS_ALERT_DELAY_MINUTES=10
```

Pour tester un autre délai ponctuellement :

```powershell
python manage.py check_gps_alerts --minutes 2
```

En production, cette commande peut être programmée avec un cron ou un job
Render.

Les opérations de gestion sont réservées au responsable. Un livreur ne voit
que ses propres missions.

## 8. Tests automatisés

Les tests utilisent temporairement SQLite afin de ne pas modifier PostgreSQL :

```powershell
$env:DB_ENGINE="sqlite"
python manage.py test
Remove-Item Env:DB_ENGINE
```

Ils vérifient les affectations uniques, l'OTP, la preuve de livraison, la clé
API GPS et les droits du livreur.

## 9. Supabase PostgreSQL

1. Créez un projet sur Supabase.
2. Ouvrez **Project Settings > Database**.
3. Copiez l'URI de connexion PostgreSQL. Pour Render, le pooler de transaction
   sur le port `6543` est généralement le plus simple.
4. Remplacez le mot de passe dans l'URI et conservez `sslmode=require` si
   Supabase l'inclut.
5. Dans Render, enregistrez l'URI complète dans `DATABASE_URL`.

Exemple :

```env
DATABASE_URL=postgresql://postgres.PROJECT_REF:MOT_DE_PASSE@aws-0-REGION.pooler.supabase.com:6543/postgres
DB_SSL_REQUIRE=True
```

Le mot de passe ne doit contenir aucun caractère non encodé dans une URL.
Encodez par exemple `@` en `%40`.

## 10. Déploiement Render

### Commandes avant GitHub

Le dépôt Git doit être initialisé dans le dossier MotoTrack, pas dans le
dossier utilisateur Windows :

```powershell
cd "C:\Users\Ninette\Documents\Projet Soutenance"
git init
git branch -M main
git remote add origin https://github.com/NinetteMame/flotte-moto-iot.git
git add .
git commit -m "Préparer MotoTrack pour Render"
git pull origin main --allow-unrelated-histories
git push -u origin main
```

Le dépôt distant contient déjà un README. Si Git signale un conflit sur
`README.md`, conservez la version complète du projet, puis exécutez :

```powershell
git add README.md
git commit -m "Fusionner la documentation MotoTrack"
git push -u origin main
```

Ne publiez jamais `.env`, `db.sqlite3`, `media/`, `.venv/` ou `staticfiles/`.
Le fichier `.gitignore` les exclut déjà.

### Création du service Render

1. Connectez-vous à Render avec votre compte GitHub.
2. Autorisez Render à accéder au dépôt `flotte-moto-iot`.
3. Dans Render, choisissez **New > Blueprint**.
4. Sélectionnez le dépôt GitHub et la branche `main`.
5. Render détecte automatiquement `render.yaml`.
6. Renseignez les variables marquées comme secrètes ou non synchronisées.

Variables à ajouter :

```env
SECRET_KEY=UNE_LONGUE_CLE_ALEATOIRE
DEBUG=False
DATABASE_URL=URI_SUPABASE
GPS_API_KEY=UNE_CLE_SECRETE_ESP32
RESPONSABLE_REGISTRATION_CODE=UN_CODE_PRIVE
DB_SSL_REQUIRE=True
ALLOWED_HOSTS=mototrack-votre-nom.onrender.com
CSRF_TRUSTED_ORIGINS=https://mototrack-votre-nom.onrender.com
MAP_PROVIDER=esri
```

`SECRET_KEY`, `GPS_API_KEY` et `RESPONSABLE_REGISTRATION_CODE` peuvent être
générées par Render. Copiez la valeur de `GPS_API_KEY` dans le programme ESP32.
N'ajoutez pas de slash final dans `ALLOWED_HOSTS`. L'origine CSRF doit commencer
par `https://`. Sur Render, MotoTrack détecte automatiquement le domaine fourni
par `RENDER_EXTERNAL_HOSTNAME`; les deux variables de domaine sont donc
facultatives tant que vous n'utilisez pas un domaine personnalisé.

### Commandes Render

Commande de build :

```text
bash build.sh
```

Cette commande installe les dépendances, collecte les fichiers statiques avec
WhiteNoise et applique les migrations sur Supabase.

Commande de démarrage :

```text
gunicorn mototrack.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

Après le premier déploiement, ouvrez le **Shell** Render :

```bash
python manage.py createsuperuser
```

Vérifiez ensuite :

```text
https://mototrack-votre-nom.onrender.com/connexion/
```

L'URL ESP32 de production devient :

```text
https://mototrack-votre-nom.onrender.com/api/gps/positions/
```

Sur une offre gratuite, Render peut mettre le service en veille. Le premier
envoi après une période d'inactivité peut donc être plus lent.

Les photos et contrats enregistrés dans `media/` sont des fichiers persistants
en local, mais le disque standard d'un service Render est éphémère. Pour les
conserver durablement en production, utilisez un disque persistant Render ou
un stockage objet comme Supabase Storage.

### Erreurs fréquentes après déploiement

- `DisallowedHost` : corrigez `ALLOWED_HOSTS` avec le domaine Render sans
  `https://`.
- `CSRF verification failed` : ajoutez l'URL Render complète avec `https://`
  dans `CSRF_TRUSTED_ORIGINS`.
- `relation does not exist` : vérifiez les logs du build et relancez
  `python manage.py migrate` depuis le Shell Render.
- Erreur de connexion Supabase : vérifiez `DATABASE_URL`, le mot de passe
  encodé dans l'URL et `DB_SSL_REQUIRE=True`.
- CSS absent : vérifiez que `collectstatic` s'est terminé et que WhiteNoise
  est placé juste après `SecurityMiddleware`.
- Erreur 403 de l'ESP32 : la valeur `GPS_API_KEY` doit être identique dans
  Render et dans le programme Arduino.

## 11. Passer du local à la production

Le code ne change pas. Seules les variables d'environnement changent :

| Paramètre | Local | Production |
|---|---|---|
| `DEBUG` | `True` | `False` |
| Base | variables `DB_*` | `DATABASE_URL` Supabase |
| SSL DB | `False` | `True` |
| Hôte | IP locale | domaine Render |
| URL ESP32 | IP du PC | HTTPS Render |
| Clé GPS | valeur du `.env` local | secret Render |

## Règles métier importantes

- Une moto ne peut avoir qu'une affectation active.
- Un livreur ne peut avoir qu'une affectation active.
- Une mission doit utiliser une paire moto/livreur actuellement affectée.
- L'OTP est généré avec six chiffres à la création.
- Un OTP correct termine la mission et crée une preuve horodatée.
- Toutes les positions GPS sont conservées dans PostgreSQL.

## Sécurité

- Utilisez des mots de passe robustes.
- Remplacez les secrets d'exemple.
- Ne versionnez jamais `.env`.
- Utilisez HTTPS en production.
- Réservez le compte superutilisateur à l'administration technique.
- La clé API simple convient à un prototype académique. Un système réel
  utiliserait une clé par appareil, une rotation des secrets et davantage de
  contrôle contre les abus.
