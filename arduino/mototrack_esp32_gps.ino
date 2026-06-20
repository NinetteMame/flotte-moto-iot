/*
  MotoTrack - ESP32 + GPS NEO-6M

  Bibliothèques à installer dans l'IDE Arduino :
  - TinyGPSPlus par Mikal Hart
  - Les bibliothèques WiFi et HTTPClient sont fournies avec l'ESP32.

  Branchement conseillé :
  NEO-6M VCC -> 3.3V ou 5V selon le module
  NEO-6M GND -> GND
  NEO-6M TX  -> ESP32 P2 / GPIO 2 (réception ESP32)
  NEO-6M RX  -> ESP32 P5 / GPIO 5 (transmission ESP32)
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <TinyGPSPlus.h>

const char* WIFI_SSID = "NOM_DU_WIFI";
const char* WIFI_PASSWORD = "MOT_DE_PASSE_WIFI";
const char* FIRMWARE_VERSION = "MotoTrack GPS v2 - immatriculation";

// Adresse IPv4 actuelle de l'ordinateur qui exécute Django.
const char* API_URL = "http://172.16.101.181:8000/api/gps/positions/";

// Production Render : décommentez cette ligne et commentez l'URL locale.
// const char* API_URL = "https://mototrack.onrender.com/api/gps/positions/";

// Utilisez exactement la même valeur que GPS_API_KEY dans Render ou .env.
const char* GPS_API_KEY = "VOTRE_CLE_API_GPS";
// L'immatriculation est plus fiable qu'un identifiant numérique, qui peut
// changer lorsqu'une moto est supprimée puis recréée dans Django.
const char* MOTO_IMMATRICULATION = "za-23-45a";
const unsigned long SEND_INTERVAL = 15000;  // Envoi toutes les 15 secondes.
const unsigned long GPS_WARNING_INTERVAL = 15000;
const int GPS_RX_PIN = 2;  // P2 : reçoit les données envoyées par TX du GPS.
const int GPS_TX_PIN = 5;  // P5 : transmet vers RX du GPS.

TinyGPSPlus gps;
HardwareSerial gpsSerial(2);
unsigned long lastSend = 0;
unsigned long lastGpsWarning = 0;

bool connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.println("Connexion Wi-Fi...");

  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED &&
         millis() - startAttempt < 20000) {
    delay(500);
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("ERREUR : connexion Wi-Fi impossible.");
    return false;
  }

  Serial.print("ESP32 connecté. IP : ");
  Serial.println(WiFi.localIP());
  return true;
}

String twoDigits(int value) {
  return value < 10 ? "0" + String(value) : String(value);
}

void sendPosition(double latitude, double longitude) {
  if (WiFi.status() != WL_CONNECTED && !connectWiFi()) {
    return;
  }

  HTTPClient http;
  http.setConnectTimeout(5000);
  http.setTimeout(5000);
  if (!http.begin(API_URL)) {
    Serial.println("ERREUR : URL API invalide.");
    return;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", GPS_API_KEY);

  String gpsDate = "";
  String gpsTime = "";

  if (gps.date.isValid()) {
    gpsDate = String(gps.date.year()) + "-" +
              twoDigits(gps.date.month()) + "-" +
              twoDigits(gps.date.day());
  }

  if (gps.time.isValid()) {
    gpsTime = twoDigits(gps.time.hour()) + ":" +
              twoDigits(gps.time.minute()) + ":" +
              twoDigits(gps.time.second());
  }

  String json = "{";
  json += "\"moto_immatriculation\":\"" + String(MOTO_IMMATRICULATION) + "\",";
  json += "\"latitude\":" + String(latitude, 7) + ",";
  json += "\"longitude\":" + String(longitude, 7);
  if (gpsDate != "") json += ",\"date_appareil\":\"" + gpsDate + "\"";
  if (gpsTime != "") json += ",\"heure_appareil\":\"" + gpsTime + "\"";
  json += "}";

  int statusCode = http.POST(json);
  Serial.print("Données envoyées : ");
  Serial.println(json);
  Serial.print("GPS : ");
  Serial.print(latitude, 6);
  Serial.print(", ");
  Serial.print(longitude, 6);

  if (statusCode == 200 || statusCode == 201) {
    Serial.println(" | Envoyé avec succès.");
  } else if (statusCode > 0) {
    Serial.print(" | Erreur HTTP ");
    Serial.println(statusCode);
  } else {
    Serial.print(" | Connexion API impossible : ");
    Serial.println(http.errorToString(statusCode));
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println();
  Serial.println(FIRMWARE_VERSION);
  Serial.print("Moto configurée : ");
  Serial.println(MOTO_IMMATRICULATION);
  gpsSerial.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  connectWiFi();
}

void loop() {
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }

  if (gps.location.isValid() &&
      gps.location.isUpdated() &&
      millis() - lastSend >= SEND_INTERVAL) {
    lastSend = millis();
    sendPosition(gps.location.lat(), gps.location.lng());
  }

  if (millis() > 10000 &&
      gps.charsProcessed() < 10 &&
      millis() - lastGpsWarning >= GPS_WARNING_INTERVAL) {
    lastGpsWarning = millis();
    Serial.println("GPS absent : vérifiez TX->P2, RX->P5 et placez le module dehors.");
  }
}
