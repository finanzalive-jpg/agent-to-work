# Collegare Atlas al tuo Google Calendar (e in futuro a Gmail)

Serve una sola volta. Al termine Atlas potrà **leggere e scrivere** il tuo Google Calendar.
Tempo: ~10 minuti. Account da usare: **finanzalive@gmail.com**.

---

## Passo 1 — Crea un progetto Google
1. Vai su **https://console.cloud.google.com** e accedi con il tuo account Google.
2. In alto, menu dei progetti → **Nuovo progetto** → nome: `Atlas Assistente` → **Crea**.
3. Assicurati che sia selezionato in alto.

## Passo 2 — Attiva l'API del Calendario
1. Menu a sinistra → **API e servizi** → **Libreria**.
2. Cerca **Google Calendar API** → aprila → **Abilita**.
   *(Più avanti, per le email, qui abiliterai anche **Gmail API**.)*

## Passo 3 — Schermata consenso OAuth
1. **API e servizi** → **Schermata consenso OAuth**.
2. Tipo utente: **Esterno** → **Crea**.
3. Compila: Nome app = `Atlas`, email di supporto = la tua, email contatto sviluppatore = la tua → **Salva e continua**.
4. "Ambiti/Scope": lascia vuoto → **Salva e continua**.
5. **Utenti di test** → **Aggiungi utenti** → inserisci **finanzalive@gmail.com** → **Salva e continua**.

## Passo 4 — Crea le credenziali
1. **API e servizi** → **Credenziali** → **Crea credenziali** → **ID client OAuth**.
2. Tipo di applicazione: **App desktop** → nome: `Atlas Desktop` → **Crea**.
3. Compare una finestra: clicca **Scarica JSON**.

## Passo 5 — Metti il file nella cartella di Atlas
1. Il file scaricato si chiama tipo `client_secret_....json`.
2. **Rinominalo esattamente** in:  `credentials.json`
3. Copialo nella cartella di Atlas, **insieme a `jarvis.py`** (la stessa dove c'è `.env`).

## Passo 6 — Installa le librerie Google
Nella cartella, apri PowerShell e lancia:
```
pip install -r requirements.txt
```

## Passo 7 — Prima autorizzazione (una volta sola)
1. Avvia Atlas e di': **"Atlas, che appuntamenti ho oggi?"** (oppure segna un appuntamento).
2. Si apre il **browser**: scegli l'account **finanzalive@gmail.com**.
3. Comparirà "**Google non ha verificato questa app**" → è normale (è la tua app personale):
   clicca **Avanzate** → **Vai a Atlas (non sicuro)**.
4. Metti la spunta per consentire l'accesso al **Calendario** → **Continua**.
5. Fatto: si crea `token_google.json` e d'ora in poi Atlas entra da solo.

---

## Da sapere
- `credentials.json` e `token_google.json` **non vanno mai su GitHub** (sono già nel `.gitignore`).
- Finché l'app è "in test", solo gli account aggiunti come **utenti di test** possono collegarsi.
  Per venderla a tanti clienti esterni serve la **verifica dell'app** di Google (si fa dopo, quando il prodotto è pronto).
- La stessa procedura, abilitando **Gmail API** e aggiungendo lo scope email, servirà per leggere/rispondere le mail.

Se qualcosa non torna, dimmi a che passo sei bloccato e ti aiuto.
