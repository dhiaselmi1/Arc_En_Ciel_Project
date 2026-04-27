# Arc En Ciel — AI Grant Finder Agent

Agent IA autonome qui recherche chaque semaine les meilleures opportunités de subventions internationales pour l'association **Arc En Ciel** (Sidi Daoued, Tunisie) — œuvrant pour l'éducation, la formation et l'intégration des enfants à déficience mentale légère, spécialement les enfants trisomiques — puis envoie un récapitulatif des **5 meilleures opportunités** par **email** et **WhatsApp**.

Le projet est conçu pour tourner **gratuitement** sur GitHub Actions, une fois par semaine, sans aucune intervention humaine.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Stack technique](#stack-technique)
- [Architecture du pipeline](#architecture-du-pipeline)
- [Installation locale](#installation-locale)
- [Configuration des variables d'environnement](#configuration-des-variables-denvironnement)
- [Lancement](#lancement)
- [Structure du projet](#structure-du-projet)
- [Schéma de la base de données](#schéma-de-la-base-de-données)
- [Logique de scoring et de tri](#logique-de-scoring-et-de-tri)
- [Déploiement GitHub Actions](#déploiement-github-actions)
- [Documentation technique](#documentation-technique)

---

## Fonctionnalités

- **Recherche web automatisée** sur 11 requêtes ciblées (FR + EN), en se basant sur Tavily (API spécialisée IA) avec un fallback DuckDuckGo.
- **Pré-filtrage par mots-clés** pour économiser les appels LLM (élimine blogs, pages d'accueil, réseaux sociaux).
- **Extraction structurée** des opportunités via Mistral AI (titre, organisation, montant, deadline, description, langue, critères d'éligibilité).
- **Évaluation d'éligibilité** par LLM contre le profil officiel d'Arc En Ciel (mission, bénéficiaires, zone géographique, secteur).
- **Scoring 0–100** pondéré : éligibilité (40%) · alignement mission (30%) · montant (15%) · deadline (15%).
- **Tri hiérarchique 4 buckets** privilégiant les opportunités complètes (montant + deadline renseignés) et jamais notifiées.
- **Stockage SQLite** avec déduplication par hash SHA256 de l'URL, machine à états (`new` → `evaluated` → `scored`/`rejected`/`expired` → `notified`).
- **Notifications doubles** : email HTML (template Jinja2) + WhatsApp (Twilio Sandbox, avec chunking automatique > 1500 caractères).
- **Cron hebdomadaire** via GitHub Actions chaque lundi à 07:00 (heure de Tunis).
- **CLI** avec flags `--dry-run`, `--stats`, `--reset-rejected` pour debug et opérations manuelles.

---

## Stack technique

| Couche | Choix | Pourquoi |
|---|---|---|
| Langage | Python 3.11+ | Écosystème IA mature, standard pour LangChain |
| Framework agent | LangChain 0.3+ | Orchestration LLM, prompts, parsers |
| LLM | Mistral AI (`mistral-small-latest`) | Accessible depuis la Tunisie (Groq et Gemini bloqués géographiquement), free tier généreux |
| Recherche web | Tavily Search API | API conçue pour agents IA, contenu web pré-nettoyé |
| Fallback recherche | DuckDuckGo (via `duckduckgo-search`) | Pas de clé requise, prend le relais si Tavily est vide |
| Stockage | SQLite | Zéro infrastructure, fichier unique versionnable comme artefact |
| Email | SMTP Gmail + App Password | Gratuit, fiable, pas d'infra dédiée |
| WhatsApp | Twilio Sandbox | Gratuit pour les tests, API simple (`whatsapp:+...`) |
| Templates | Jinja2 | Standard Python, séparation logique/présentation |
| Hébergement | GitHub Actions (cron) | Gratuit, intégré au repo, secrets sécurisés |
| Documentation | python-docx | Génération du dossier technique `.docx` |

---

## Architecture du pipeline

```
           ┌──────────────────────────────────────────┐
           │         GitHub Actions (cron lundi 6h)    │
           └────────────────────┬──────────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │   src/main.py        │
                    │   run_pipeline()     │
                    └───────────┬──────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
   ┌────▼─────┐         ┌───────▼──────┐         ┌─────▼──────┐
   │  STEP 1  │         │   STEP 2     │         │   STEP 3   │
   │  Fetch   │  ──►    │  Eligibility │  ──►    │  Ranking   │
   └────┬─────┘         └──────┬───────┘         └──────┬─────┘
        │                      │                        │
        │ Tavily/DDG            │ LLM verdict             │ LLM score 0-100
        │ → pré-filtrage        │ ELIGIBLE /              │ + tri 4 buckets
        │ → LLM extract JSON    │ POTENTIALLY /           │ (complete/incomplete
        │ → upsert SQLite       │ NOT_ELIGIBLE            │  × new/old)
        │                      │                        │
        └──────────────────────┴────────────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │   STEP 4 — Digest    │
                    │   Top 5 opportunités │
                    └───────┬──────┬───────┘
                            │      │
                       Email │      │ WhatsApp
                       (SMTP)│      │ (Twilio)
                            ▼      ▼
                       Destinataire(s)
```

Chaque étape est **idempotente** : relancer le pipeline ne crée pas de doublons (dédup par `url_hash` + transitions de status contrôlées).

---

## Installation locale

### Prérequis

- Python **3.11** ou supérieur
- Un compte sur **Mistral AI** ([console.mistral.ai](https://console.mistral.ai)) → API key
- Un compte sur **Tavily** ([tavily.com](https://tavily.com)) → API key (1 000 recherches/mois gratuites)
- Un compte **Gmail** avec **2FA activée** + **App Password** ([myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords))
- Un compte **Twilio** avec **WhatsApp Sandbox activé** ([console.twilio.com](https://console.twilio.com))

### Étapes

```bash
# 1. Cloner
git clone https://github.com/<user>/Arc_En_Ciel_Project.git
cd Arc_En_Ciel_Project

# 2. Environnement virtuel
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 3. Dépendances
pip install -r requirements.txt

# 4. Configuration
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
# puis éditer .env avec tes vraies clés
```

---

## Configuration des variables d'environnement

Crée un fichier `.env` à la racine en t'inspirant de `.env.example` :

| Variable | Exemple | Description |
|---|---|---|
| `MISTRAL_API_KEY` | `xxxxxx...` | Clé API Mistral (obligatoire) |
| `MISTRAL_MODEL` | `mistral-small-latest` | Modèle à utiliser |
| `TAVILY_API_KEY` | `tvly-xxxxxx...` | Clé API Tavily (obligatoire) |
| `SMTP_HOST` | `smtp.gmail.com` | Serveur SMTP |
| `SMTP_PORT` | `587` | Port TLS |
| `SMTP_USER` | `marzoukagent@gmail.com` | Adresse expéditrice |
| `SMTP_APP_PASSWORD` | `xxxx xxxx xxxx xxxx` | App Password Gmail (16 chars, sans espaces) |
| `EMAIL_FROM_NAME` | `Agent Arc En Ciel` | Nom affiché de l'expéditeur |
| `EMAIL_TO` | `destinataire@example.com` | Adresse du destinataire |
| `TWILIO_ACCOUNT_SID` | `ACxxxxxx...` | SID Twilio |
| `TWILIO_AUTH_TOKEN` | `xxxxxx...` | Token Twilio |
| `TWILIO_WHATSAPP_FROM` | `whatsapp:+14155238886` | Numéro fixe sandbox Twilio |
| `WHATSAPP_TO` | `whatsapp:+21693105718` | Numéro WhatsApp destinataire (au format `whatsapp:+216...`) |
| `DB_PATH` | `data/grants.db` | Chemin du fichier SQLite |

> ⚠️ Le destinataire WhatsApp doit avoir **rejoint la sandbox Twilio** au préalable en envoyant le code `join <ton-mot-de-passe-sandbox>` au numéro Twilio. Le lien expire toutes les 72h en mode sandbox.

---

## Lancement

### Pipeline complet

```bash
python -m src.main
```

Exécute les 4 étapes : **Fetch** → **Eligibility** → **Ranking** → **Digest**.

### Mode dry-run (sans envoi)

```bash
python -m src.main --dry-run
```

Tourne le pipeline mais saute l'envoi email/WhatsApp — utile pour tester sans spammer.

### Voir l'état de la base

```bash
python -m src.main --stats
```

Affiche un récap : total grants, répartition par status, et un tableau détaillé.

### Réinitialiser les rejets (après assouplissement du prompt d'éligibilité)

```bash
python -m src.main --reset-rejected
```

Repasse tous les grants `rejected` en `new` pour qu'ils soient ré-évalués au prochain run.

---

## Structure du projet

```
Arc_En_Ciel_Project/
├── .github/
│   └── workflows/
│       └── weekly.yml                  # cron hebdomadaire GitHub Actions
├── config/
│   └── association_profile.json        # profil Arc En Ciel (mission, cible, critères)
├── data/
│   └── grants.db                       # SQLite (gitignored, persisté en artefact)
├── docs/
│   └── Documentation_Technique_Arc_En_Ciel.docx
├── scripts/
│   └── generate_doc.py                 # génération du dossier technique .docx
├── src/
│   ├── main.py                         # entrée CLI + run_pipeline()
│   ├── config.py                       # Settings (dataclass) + load_settings/load_profile
│   ├── db.py                           # init schema + connect + upsert_grant (dédup SHA256)
│   ├── search/
│   │   ├── tavily_search.py            # client Tavily API
│   │   └── ddg_fallback.py             # fallback DuckDuckGo
│   ├── agent/
│   │   ├── llm.py                      # build_llm() + throttle() (5s entre appels)
│   │   ├── prompts.py                  # SYSTEM_AGENT, EXTRACT, ELIGIBILITY, RANKING, SEARCH_QUERIES
│   │   ├── fetcher.py                  # STEP 1 — fetch + extract + store
│   │   ├── eligibility.py              # STEP 2 — verdict ELIGIBLE/POTENTIALLY/NOT
│   │   └── ranker.py                   # STEP 3 — score 0-100 + top_n() avec tri 4 buckets
│   ├── notifications/
│   │   ├── digest.py                   # orchestration email + WhatsApp
│   │   ├── email_sender.py             # SMTP TLS via smtplib
│   │   └── whatsapp_sender.py          # Twilio Client + chunking > 1500 chars
│   └── templates/
│       └── weekly_email.txt            # template Jinja2 du digest
├── tests/                              # (à compléter)
├── .env.example                        # template variables d'environnement
├── requirements.txt
└── README.md
```

---

## Schéma de la base de données

Table unique `grants` :

| Colonne | Type | Description |
|---|---|---|
| `id` | INTEGER PK | auto-increment |
| `url_hash` | TEXT UNIQUE | SHA256 de `source_url` (déduplication) |
| `title` | TEXT | titre de l'opportunité |
| `organization` | TEXT | bailleur / fondation |
| `amount` | TEXT | montant en texte libre (ex: `10 000 USD`) |
| `deadline` | TEXT | date limite (`AAAA-MM-JJ` ou `non spécifié`) |
| `source_url` | TEXT | URL d'origine |
| `description` | TEXT | résumé en français (1-2 phrases) |
| `language` | TEXT | `fr` / `en` / `ar` |
| `eligibility` | TEXT | verdict + raison concaténés |
| `score` | REAL | score 0-100 |
| `score_reason` | TEXT | justification du score (1 phrase) |
| `status` | TEXT | `new` / `evaluated` / `scored` / `rejected` / `expired` / `notified` |
| `fetched_at` | TEXT | ISO 8601 (insertion) |
| `notified_at` | TEXT | ISO 8601 (envoi digest) |

**Index** : `status`, `score`, `deadline`.

### Machine à états

```
                  fetcher
                     │
               ┌─────▼─────┐
               │    new    │
               └─────┬─────┘
                     │ eligibility.evaluate_pending()
               ┌─────▼─────┐
               │ evaluated │
               └─────┬─────┘
                     │ ranker.rank_all()
                     │
   ┌─────────────────┼─────────────────┐
   │                 │                 │
┌──▼──┐         ┌────▼───┐        ┌────▼────┐
│scored│        │rejected│        │ expired │
└──┬───┘        └────────┘        └─────────┘
   │ digest.send_weekly_digest()
┌──▼──────┐
│notified │ ◄── peut être ré-inclus dans le top_n
└─────────┘    (bucket "old")
```

---

## Logique de scoring et de tri

### Scoring (0-100, pondéré)

| Critère | Poids | Détail |
|---|---|---|
| Éligibilité | **40%** | `ELIGIBLE` = 40 · `POTENTIALLY_ELIGIBLE` = 20 · `NOT_ELIGIBLE` = 0 (jamais scoré) |
| Alignement mission | **30%** | trisomie / inclusion / éducation spécialisée / atelier pâtisserie / mobilier |
| Montant | **15%** | idéal 5–50 k$ → 15 · raisonnable hors fourchette → 7 · sinon → 0 |
| Deadline | **15%** | > 30j → 15 · 7-30j → 10 · < 7j → 5 · passée → 0 |

### Tri du top N (4 buckets hiérarchiques)

Quand on construit le digest, les 5 meilleures opportunités sont sélectionnées dans cet ordre **strict** :

1. **complete_new** — montant + deadline renseignés ET jamais envoyée
2. **complete_old** — montant + deadline renseignés mais déjà envoyée précédemment
3. **incomplete_new** — info manquante mais jamais envoyée
4. **incomplete_old** — info manquante et déjà envoyée

À l'intérieur de chaque bucket, tri par **score décroissant**. Cette logique garantit que la destinataire reçoit toujours **5 opportunités** (même en début de pipeline avec peu de données complètes), tout en privilégiant la qualité.

### Règle d'or de l'éligibilité

> *Dans le doute, NE REJETTE PAS.*

Le prompt d'éligibilité est volontairement permissif : seul un critère d'exclusion **explicite et sans ambiguïté** (ex : *"Reserved for US-based organizations only"*) déclenche un `NOT_ELIGIBLE`. Tout le reste tombe en `POTENTIALLY_ELIGIBLE` — l'utilisateur final tranche en lisant la page source.

---

## Déploiement GitHub Actions

Le workflow `.github/workflows/weekly.yml` tourne automatiquement **chaque lundi à 06:00 UTC** (07:00 Tunis). Il peut aussi être déclenché manuellement via l'onglet **Actions → Weekly grant digest → Run workflow**.

### Secrets requis (Settings → Secrets and variables → Actions)

| Nom | Valeur |
|---|---|
| `MISTRAL_API_KEY` | clé Mistral |
| `TAVILY_API_KEY` | clé Tavily |
| `SMTP_USER` | adresse Gmail expéditrice |
| `SMTP_APP_PASSWORD` | App Password Gmail (16 chars) |
| `EMAIL_TO` | destinataire email |
| `TWILIO_ACCOUNT_SID` | SID Twilio |
| `TWILIO_AUTH_TOKEN` | token Twilio |
| `TWILIO_WHATSAPP_FROM` | `whatsapp:+14155238886` |
| `WHATSAPP_TO` | `whatsapp:+216XXXXXXXX` |

> Les noms de secrets doivent être en **MAJUSCULES** (le workflow référence `${{ secrets.MISTRAL_API_KEY }}`, etc.).

### Artefact

À chaque run, le fichier `data/grants.db` est uploadé comme artefact GitHub (rétention **30 jours**) sous le nom `grants-db-<run-id>` — utile pour debug ou audit historique.

---

## Documentation technique

Une documentation `.docx` exhaustive (architecture, choix technos, base de données, prompts, déploiement) est disponible :

```
docs/Documentation_Technique_Arc_En_Ciel.docx
```

Régénérer :

```bash
python scripts/generate_doc.py
```

---

## Auteurs

Projet de Fin d'Études — encadré pour l'association **Arc En Ciel** (Tunisie).
