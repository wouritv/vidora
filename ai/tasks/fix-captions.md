## update a faire
- Creer une table transcription dans laquelle pour chaque reel ou sous-titre traité, il faudrait stocker le texte transcript complet venant d'assembly et le cas echeant de faster-whisper. l'idee etant que la transcription dois se faire une seule fois pour chaque reel ou sous-titre et que l'on puisse ensuite reutiliser cette transcription pour d'autres taches (ex: sous-titre, correction, traduction, etc.)
- il faudrait aussi stocker en bd les traductions si jamais le user en fait, de cette maniere si jamais il veut voir la traduction dans une autre langue, on ne relance pas la traduction mais on reutilise celle qui est deja stockée.
- si a l'ouverture d'un reel ou sous-titre, il n'y a pas de transcription dans la table, alors on lance la transcription et on stocke le resultat dans la table. si la transcription existe deja, on ne relance pas la transcription.
- il faudrait avoir une table qui pour un reel/captions stocke l'historique des modifications faite lors de l'edition de style (Version 1
  ├── captions: true
  ├── font: Arial
  └── color: white

Version 2
├── captions: true
├── font: Montserrat
└── color: white

Version 3
├── captions: true
├── font: Montserrat
├── color: yellow
└── zoom: true)
- pour chaque edition du user, on conserve la video originale, on cree une  nouvelle a partir de la source et sur laquelle on applique tous les changements et on stocke le resultat dans la table. l'idee etant que l'on puisse revenir a n'importe quelle version precedente.
  Le principe idéal pour Vireel
  VIDEO SOURCE
  │
  │
  + configuration
  │
  ▼
  RENDU #1
  │
  ┌──────┴──────┐
  │             │
  modifier       annuler
  │             │
  ▼             ▼
  RENDU #2       RENDU #1

Par exemple :

Source :

video-originale.mp4

L'utilisateur ajoute :

Sous-titres
+ police Montserrat
  + texte blanc
  + animation

Vireel produit :

output-v1.mp4

Ensuite il ajoute :

Zoom
+ image en bas

Tu ne modifies pas output-v1.mp4.

Tu repars de :

video-originale.mp4
+
configuration précédente
  +
nouveaux changements
↓
output-v2.mp4

- l'utilisateur vera a chaque moment la derniere version de la video, que ce soit dans la previuasilisation, le rendu final, le telechargement ou le partage social. A cote du bouton Edition de style, il faudrait afficher un bouton reset pour revenir a la version originale de la video. Le bouton reset supprime tout l'historique des modifications et revient a la video originale. 
- pour chaque operation (reels, sous-titres, edition de style, traduction, etc.), il faudrait stocker les informations de details de facturation pour chaque service utilisé (ex: assembly, openIa, Vps, ..) qui ont servit pour determiner le cout de l'operation. L'idee etant que l'on puisse ensuite faire un suivi du cout de chaque operation et de chaque reel ou sous-titre. Si jamais la table concerné n'a pas de colonne pour stocker les informations de facturation, il faudrait en ajouter une.
- la logique de calcul des credits pour les operations reels, sous-titres, edition de style, traduction, etc. a changer, pour chaque requete sur openIA ou Gemini, integrer la recuperation du nombre de token consommes en input et output (souvent presenté comme ceci pour openIA : "usage": {
  "prompt_tokens": 15,
  "completion_tokens": 42,
  "total_tokens": 57
  } ou comme ceci pour Gemini : "usageMetadata": {
  "promptTokenCount": 15,
  "candidatesTokenCount": 42,
  "totalTokenCount": 57
  }, se fier au doc officielle pour savoir la bonne maniere de recuperer le nombre de token consommes pour chaque requete. Ensuite il ne faudrait plus utiliser les variables OPEN_IA_ESTIMATE_COST_PER_MINUTE et GEMINI_ESTIMATE_COST_PER_MINUTE. mais plutot OPEN_IA_INPUT_TOKEN_PER_DOLLAR et OPEN_IA_OUTPUT_TOKEN_PER_DOLLAR pour openIA et GEMINI_INPUT_TOKEN_PER_DOLLAR et GEMINI_OUTPUT_TOKEN_PER_DOLLAR pour Gemini. Ensuite, pour chaque operation reels, sous-titres, edition de style, traduction, etc., il faudrait calculer le cout reel de l'operation en fonction du nombre de token consommes et du cout par token. L'idee etant que l'on puisse avoir un suivi precis du cout reel de chaque operation et de chaque reel ou sous-titre. De cette maniere on aura le cout USD pour chaque operation reels, sous-titres, edition de style, traduction, etc. et on pourra ensuite calculer le cout total pour chaque reel ou sous-titre. Il faudrait aussi stocker le cout total pour chaque reel ou sous-titre dans la table correspondante. Le reste des elements de facturation (ex: cout du VPS, cout du stockage, etc.) restent valide dans la logique actuelle. 
- il faudrait aussi valider que la gestion du stockage des reels et sous-titres est bien faite, pour chaque operation entrainant un stockage, il faudrait stocker le volume utilisé puis deduire ce volume du volume restant a l'utilisateur. 
- Sur la page Landing, le bouton "Acceder a la console" dois avoir une couleur de texte blanche aussi bien en mode sombre que mode clair
- revoir la page de login pour lui donner un look plus epurer et plus moderne, avec un design plus minimaliste et des couleurs plus douces. La rendre fonctionnelle et adapté au mode claire/sombre.