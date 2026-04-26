# Arc En Ciel — AI Grant Finder Agent

Agent IA qui recherche chaque semaine les meilleures opportunités de subventions pour l'association **Arc En Ciel** (Sidi Daoued, Tunisie) et envoie un récap par **email + WhatsApp**.

## Stack

- Python 3.11+
- LangChain + Mistral AI (LLM)
- Tavily Search (recherche web) + DuckDuckGo (fallback)
- SQLite (stockage opportunités)
- SMTP Gmail (email) + Twilio (WhatsApp)
- GitHub Actions (cron hebdomadaire)

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # puis remplir les valeurs
```

## Lancement manuel

```bash
python -m src.main
```

## Structure

```
src/
├── main.py                     # entrée principale
├── config.py                   # chargement .env + profil
├── db.py                       # SQLite
├── search/                     # outils de recherche web
├── agent/                      # logique LangChain (fetch, eligibility, ranking)
├── notifications/              # email + WhatsApp
└── templates/                  # template du digest hebdo
config/
└── association_profile.json    # profil Arc En Ciel
data/
└── grants.db                   # SQLite (gitignored)
```
