"""
google_cal.py - Collegamento ad Google Calendar (lettura + scrittura).

Atlas legge e scrive il TUO Google Calendar (calendario 'primary').
Autorizzazione una tantum via OAuth:
  1) metti il file  credentials.json  (scaricato da Google Cloud) nella cartella del progetto
  2) alla prima richiesta di calendario, si apre il browser per autorizzare -> crea token_google.json
Dopo, funziona da solo.

Vedi GUIDA_GOOGLE.md per i passaggi su Google Cloud.
"""
import os
import datetime

SCOPES = ["https://www.googleapis.com/auth/calendar"]

_BASE = os.path.dirname(os.path.abspath(__file__))
CREDENZIALI = os.path.join(_BASE, "credentials.json")
TOKEN = os.path.join(_BASE, "token_google.json")


def configurato():
    """True se è presente il file credentials.json (Google collegato o collegabile)."""
    return os.path.exists(CREDENZIALI)


def _service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENZIALI):
                raise RuntimeError("Manca credentials.json: Google non è ancora collegato.")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENZIALI, SCOPES)
            creds = flow.run_local_server(port=0)   # apre il browser per autorizzare
        with open(TOKEN, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def _local(dt_naive_iso):
    """Da 'YYYY-MM-DDTHH:MM:SS' naive all'ISO con fuso orario locale del PC."""
    return datetime.datetime.fromisoformat(dt_naive_iso).astimezone()


def crea_evento(titolo, data, ora, durata_min=60, luogo=""):
    """Crea un evento sul Google Calendar. Torna il link all'evento."""
    svc = _service()
    inizio = _local(f"{data}T{ora}:00")
    fine = inizio + datetime.timedelta(minutes=int(durata_min or 60))
    body = {
        "summary": titolo or "Appuntamento",
        "location": luogo or "",
        "start": {"dateTime": inizio.isoformat()},
        "end": {"dateTime": fine.isoformat()},
    }
    ev = svc.events().insert(calendarId="primary", body=body).execute()
    return ev.get("htmlLink", "")


def eventi_del_giorno(data_iso):
    """Lista eventi del giorno dal Google Calendar. Torna [{'titolo','ora','luogo'}...]."""
    svc = _service()
    inizio = _local(f"{data_iso}T00:00:00")
    fine = inizio + datetime.timedelta(days=1)
    res = svc.events().list(
        calendarId="primary",
        timeMin=inizio.isoformat(),
        timeMax=fine.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    out = []
    for e in res.get("items", []):
        s = e.get("start", {})
        quando = s.get("dateTime") or s.get("date") or ""
        ora = quando[11:16] if "T" in quando else "tutto il giorno"
        out.append({"titolo": e.get("summary", "(senza titolo)"),
                    "ora": ora, "luogo": e.get("location", "")})
    return out
