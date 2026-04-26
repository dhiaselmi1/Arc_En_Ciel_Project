"""LLM prompts used by the agent."""

SYSTEM_AGENT = """\
Tu es un assistant spécialisé dans la recherche de subventions pour les ONG.
Tu travailles pour l'association Arc En Ciel (Tunisie), qui œuvre pour
l'éducation, la formation et l'intégration des enfants à déficience mentale
légère, spécialement les enfants trisomiques.

Règles strictes :
- Maximum 5 opportunités par cycle, classées de la meilleure à la moins bonne.
- Langue : français en priorité ; traduis si la source est en anglais ou arabe.
- Ton : simple, clair, professionnel.
- Chaque opportunité doit être pertinente pour le projet d'Arc En Ciel
  (mobilier, atelier pâtisserie, enfants trisomiques, inclusion).
- Exclure toute opportunité dont la deadline est dépassée.
"""

EXTRACT_GRANT_FROM_RESULT = """\
Voici un résultat de recherche web. Si — et seulement si — il décrit une
opportunité de subvention/grant/appel à projet concrète et active, extrais
les informations dans un JSON STRICT au format suivant :

{{
  "is_grant": true,
  "title": "...",
  "organization": "...",
  "amount": "ex: 10 000 USD ou 'non spécifié'",
  "deadline": "AAAA-MM-JJ ou 'non spécifié'",
  "description": "1-2 phrases en français",
  "language": "fr|en|ar",
  "eligibility": "résumé court des critères"
}}

Si ce n'est PAS une vraie opportunité de subvention (ex: article général,
page d'accueil, blog) :

{{ "is_grant": false }}

Réponds UNIQUEMENT avec le JSON, rien d'autre.

Source URL : {url}
Titre : {title}
Contenu : {content}
"""

ELIGIBILITY_PROMPT = """\
Tu dois évaluer si l'association Arc En Ciel peut postuler à cette subvention.

PROFIL DE L'ASSOCIATION :
{profile_json}

OPPORTUNITÉ :
Titre : {title}
Organisation : {organization}
Montant : {amount}
Description : {description}
Critères d'éligibilité connus : {eligibility}
Source : {source_url}

Évalue strictement et réponds UNIQUEMENT en JSON :

{{
  "verdict": "ELIGIBLE" | "POTENTIALLY_ELIGIBLE" | "NOT_ELIGIBLE",
  "reason": "1-2 phrases en français expliquant le verdict",
  "blockers": ["liste des points bloquants si NOT_ELIGIBLE, sinon []"]
}}

Règle d'or : **dans le doute, NE REJETTE PAS**. Mieux vaut un POTENTIALLY_ELIGIBLE qu'un
NOT_ELIGIBLE à tort — l'utilisateur final ira lire la page pour confirmer.

Critères :
- NOT_ELIGIBLE UNIQUEMENT si une exclusion EXPLICITE et SANS AMBIGUÏTÉ est mentionnée dans
  les critères. Exemples valides de NOT_ELIGIBLE :
    * "Reserved for US-based organizations only"
    * "Réservé aux ONG françaises"
    * "Open to Canadian charities"
    * Bénéficiaires explicitement non concernés (ex: réservé aux personnes âgées uniquement)
  Si l'opportunité mentionne juste un focus régional (ex: "priorité à l'Afrique", "MENA region")
  sans EXCLURE explicitement la Tunisie → ce n'est PAS NOT_ELIGIBLE.

- ELIGIBLE quand l'opportunité mentionne explicitement la Tunisie, le Maghreb, le MENA,
  l'Afrique du Nord, l'Afrique en général, ou les pays à revenu faible/intermédiaire,
  ET le secteur (handicap/éducation/inclusion) correspond clairement.

- POTENTIALLY_ELIGIBLE par défaut dans tous les autres cas (infos manquantes, ambiguïté,
  zone géo non précisée, etc.).
"""

RANKING_PROMPT = """\
Tu dois noter cette opportunité de subvention pour l'association Arc En Ciel.

PROFIL :
{profile_json}

OPPORTUNITÉ :
Titre : {title}
Organisation : {organization}
Montant : {amount}
Date limite : {deadline}
Description : {description}
Verdict éligibilité : {eligibility_verdict}

Donne un score de 0 à 100 selon ces poids :
- Éligibilité (40%) : ELIGIBLE=40, POTENTIALLY=20, NOT=0
- Alignement mission (30%) : pertinence vs trisomie/inclusion/éducation spécialisée/atelier pâtisserie/mobilier
- Montant (15%) : idéal entre 5 000 $ et 50 000 $ → 15 ; en dehors mais raisonnable → 7 ; hors fourchette → 0
- Deadline (15%) : >30 jours → 15 ; 7-30 jours → 10 ; <7 jours → 5 ; passée → 0

Réponds UNIQUEMENT en JSON :

{{
  "score": 0-100,
  "reason": "1 phrase courte en français expliquant le score, ex: 'Match fort — cible ONG handicap MENA, montant idéal'"
}}
"""

SEARCH_QUERIES = [
    "subventions ONG Tunisie inclusion handicap 2026",
    "appel à projets enfants trisomie 21 Tunisie",
    "grants disability inclusion children NGO Tunisia 2026 2027",
    "financement éducation spécialisée Maghreb 2026",
    "appel à projets formation professionnelle handicap MENA",
    "international grants special education NGO 2026 2027",
    "down syndrome NGO grants Africa funding 2026",
    "intellectual disability foundation grants international 2026",
    "appel à projets autonomie inclusion Afrique 2026",
    "grants for children with disabilities Africa MENA 2026",
    "fondation handicap mental subvention international 2026",
]
