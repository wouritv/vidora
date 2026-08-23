15. Modal Édition automatique

Le modal doit présenter les options sous forme de switch / boutons ON-OFF.

Édition automatique


Zoom              [ OFF ]
Luminosité        [ OFF ]
Saturation        [ OFF ]
Contraste         [ OFF ]
Vitesse           [ OFF ]
Remove silence    [ OFF ]
Clean audio       [ OFF ]
Remove bad takes  [ OFF ]


                         [ Appliquer ]

Aucune modification ne doit être appliquée tant que l'utilisateur n'a pas validé.

16. Fonctionnalités d'édition automatique
    Zoom

Permettre d'appliquer automatiquement un zoom au Reel selon les paramètres définis par le moteur vidéo.

Privilégier une solution open source existante lorsque celle-ci est suffisamment fiable.

Sinon développer la logique dans video-engine.

Luminosité

Ajustement automatique de la luminosité.

Saturation

Ajustement automatique de la saturation.

Contraste

Ajustement automatique du contraste.
Vitesse

Permettre de modifier automatiquement la vitesse du Reel.

La valeur exacte devra être définie dans les paramètres du traitement.

17. Remove Silence

Détecter les périodes de silence et les supprimer automatiquement.

Le système doit utiliser en priorité une solution open source éprouvée si elle existe.

Sinon développer une détection basée sur l'analyse audio.

Le résultat doit conserver une synchronisation correcte avec :

la vidéo ;
le transcript ;
les sous-titres.

18. Clean Audio

Nettoyer automatiquement l'audio du Reel.

Rechercher en priorité une solution open source adaptée.

Le traitement peut inclure notamment :

réduction du bruit ;
normalisation ;
amélioration de la voix ;
équilibrage audio.

Il faut éviter d'ajouter une API payante si une solution locale suffisamment performante existe.

19. Remove Bad Takes

Cette fonctionnalité doit exploiter la transcription AssemblyAI déjà disponible.

Principe :

Transcript
↓
Analyse du contenu
↓
Détection des passages considérés comme "bad takes"
↓
Identification des timestamps
↓
Suppression des segments vidéo
↓
Réassemblage du Reel

Exemples potentiels :

répétitions ;
phrases interrompues ;
hésitations importantes ;
reprises ;
erreurs explicitement corrigées ;
passages abandonnés.

L'IA ne doit pas supprimer arbitrairement du contenu.

Elle doit produire une liste de segments candidats :

{
"start": 12.4,
"end": 15.8,
"reason": "repeated phrase",
"confidence": 0.91
}

Puis le moteur vidéo applique les suppressions.

20. IA open source

Pour chaque fonctionnalité d'édition automatique :

Existe-t-il une solution open source fiable ?
│
oui
│
▼
Utiliser la solution locale
│
non
│
▼
Développer un algorithme Vireel

L'objectif est de limiter les coûts récurrents des APIs externes.

Les solutions doivent cependant être évaluées selon :

qualité ;
performance ;
consommation CPU/GPU ;
licence ;
facilité d'intégration ;
stabilité ;
compatibilité Docker.
21. Architecture recommandée

Les fonctionnalités doivent être organisées autour de pipelines réutilisables.

video-engine/
│
├── pipelines/
│   ├── subtitle-processing-pipeline
│   ├── reel-processing-pipeline
│   └── auto-edit-pipeline
│
├── subtitles/
│   ├── subtitle-generator
│   ├── subtitle-editor
│   ├── subtitle-style
│   └── translation
│
├── audio/
│   ├── silence-removal
│   └── audio-cleaning
│
├── video/
│   ├── zoom
│   ├── brightness
│   ├── saturation
│   ├── contrast
│   └── speed
│
└── bad-takes/
└── bad-take-detector
22. Réutilisation des données

Le système doit éviter de refaire des traitements déjà effectués.

Par exemple :

                  VIDEO
                    │
                    ▼
              TRANSCRIPTION
                    │
           ┌────────┼─────────┐
           ▼        ▼         ▼
       SOUS-TITRES REELS   HIGHLIGHTS
           │        │
           │        ▼
           │   REMOVE BAD TAKES
           │
           ▼
       TRANSLATION

Une transcription déjà disponible doit être réutilisée par toutes les fonctionnalités qui en ont besoin.

23. Gestion des coûts et crédits

Toutes les opérations IA doivent passer par le système central de coûts.

Exemple :

Sous-titres
├── transcription AssemblyAI
├── traduction éventuelle
└── rendering


Reel
├── transcript existant ?
├── analyse IA
├── génération
├── captions
└── rendering


Remove bad takes
├── transcript existant ?
├── analyse IA
└── rendering

Avant chaque opération :

Estimate cost
↓
Calculate credits
↓
Check balance
↓
Reserve credits
↓
Execute
↓
Actual cost
↓
Consume / Release
24. Résultat attendu côté utilisateur

Le parcours doit finalement être extrêmement simple.

Sous-titres
Upload vidéo
↓
Génération automatique
↓
Sous-titres
↓
Édition des lignes
↓
Style
↓
Traduction
↓
Export
Reels
Vidéo
↓
Génération des Reels
↓
Sélection d'un Reel
↓
Sous-titres
│
├── Modifier ligne
├── Édition de style
├── Traduction
└── Appliquer à tous
↓
Édition automatique
│
├── Zoom
├── Luminosité
├── Saturation
├── Contraste
├── Vitesse
├── Remove silence
├── Clean audio
└── Remove bad takes
↓
Export
