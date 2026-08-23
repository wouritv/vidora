Task — Refonte Sous-titres, Captions et Édition automatique des Reels
1. Objectif

Réintroduire dans Vireel la fonctionnalité Sous-titres supprimée précédemment et harmoniser son fonctionnement avec l'édition des captions disponible dans les Reels.

L'objectif est de simplifier l'expérience utilisateur en :

supprimant les étapes inutiles du workflow Sous-titres ;
utilisant une interface unique et cohérente pour l'édition des sous-titres/captions ;
permettant de personnaliser le style des captions directement depuis les lignes ;
permettant de traduire les sous-titres ;
permettant d'appliquer les modifications à toutes les lignes ;
améliorant le fonctionnement de l'édition automatique des Reels ;
réutilisant au maximum la transcription existante afin d'éviter les traitements IA inutiles.
2. Fonctionnalité « Sous-titres »
   2.1 Réintroduire la fonctionnalité

Réintroduire complètement la fonctionnalité Captions, mais la présenter à l'utilisateur sous le nom :

Sous-titres

Le terme « captions » ne doit plus être utilisé comme nom de fonctionnalité dans l'interface utilisateur.

La fonctionnalité doit également conserver les données nécessaires en base de données.

Workflow

Le parcours utilisateur doit être simplifié.

Ancien workflow :

Upload vidéo
↓
Étape 1
↓
Étape 2
↓
Étape 3
↓
Étape 4
↓
Sous-titres

Nouveau workflow :

Upload vidéo
↓
Transcription AssemblyAI
↓
Génération des sous-titres
↓
Éditeur Sous-titres

L'objectif est de générer directement les sous-titres après la transcription.

3. Réutilisation de la transcription

La transcription AssemblyAI doit être considérée comme une ressource réutilisable.

Si une transcription existe déjà pour la vidéo, elle doit être réutilisée.

Exemple :

Vidéo
│
▼
Transcript AssemblyAI
│
├── Sous-titres
├── Reels
├── Highlights
├── Traduction
└── Remove bad takes

Il ne faut donc pas relancer AssemblyAI lorsqu'une transcription valide existe déjà.

Cette logique doit être compatible avec le système de cache et de maîtrise des coûts IA de Vireel.

4. Édition des Sous-titres

Après génération, l'utilisateur arrive directement dans l'éditeur.

L'éditeur doit permettre :

modification du texte ;
modification des mots directement dans les lignes ;
modification du style ;
modification de la police ;
modification de la taille ;
modification de la couleur ;
modification des animations ;
traduction ;
application d'un style à toutes les lignes.

L'interface doit privilégier une édition directement sur les lignes de sous-titres.

5. Refonte de l'édition des Reels

Dans l'éditeur de Reels, les fonctionnalités actuellement séparées :

Captions
Sous-titres

doivent être fusionnées.

L'utilisateur doit désormais avoir un seul menu :

Sous-titres

Ce menu devient le point central de gestion des captions du Reel.

6. Menu Sous-titres du Reel

Le menu doit contenir principalement :

┌──────────────────────────────┐
│ Sous-titres                  │
│                              │
│ [ Traduction ] [ ... ]       │
│                              │
│ Ligne 1                      │
│ Ligne 2                      │
│ Ligne 3                      │
│ Ligne 4                      │
│                              │
│ [ Appliquer à tous ]         │
└──────────────────────────────┘

Lorsqu'une ligne est sélectionnée, le bouton :

Édition de style

devient actif.

7. Édition de style

Ajouter en haut du menu Sous-titres :

Édition de style

Le bouton doit être activé lorsqu'une ligne de sous-titre est sélectionnée.

Lorsqu'il est sélectionné, ouvrir un modal.

Modal

Le modal doit permettre de modifier en temps réel :

police ;
taille ;
couleur ;
couleur de surbrillance ;
animation ;
épaisseur ;
contour ;
arrière-plan ;
espacement ;
autres paramètres de style déjà disponibles dans l'ancien éditeur Sous-titres.

Les changements doivent être visibles immédiatement sur le Reel.

Aucun bouton « Enregistrer » intermédiaire ne doit être nécessaire pour visualiser le résultat.

8. Navigation du modal

Le modal d'édition de style doit comporter une icône :

← Retour

Cette icône permet de revenir au menu principal Sous-titres.

Le workflow devient :

Sous-titres
│
├── sélectionner une ligne
│
▼
Édition de style
│
├── Police
├── Taille
├── Couleur
├── Animation
├── etc.
│
└── ← Retour
│
▼
Sous-titres

9. Nettoyage de l'ancien éditeur Captions

Supprimer de l'interface Captions les éléments devenus redondants.

À supprimer
Taille de la ligne
Police de la ligne
Modifier le texte
Bloc « Police »
Bloc « Animation »
Bloc « Couleur »
Bloc « Mot sélectionné »

La modification du texte doit se faire directement dans la ligne.

La personnalisation du style doit être centralisée dans :

Édition de style

Cela évite d'avoir plusieurs endroits permettant de modifier la même propriété.

10. Appliquer à tous

Conserver le bouton :

Appliquer à tous

Ce bouton applique le style de la ligne actuellement sélectionnée à toutes les lignes du Reel.

Exemple :

Ligne sélectionnée
│
▼
Style personnalisé
│
▼
[ Appliquer à tous ]
│
▼
Toutes les lignes
11. Traduction

Ajouter dans le menu Sous-titres une section :

Traduction

La traduction ne doit pas être exécutée automatiquement lorsque l'utilisateur active le bloc.

Le fonctionnement doit être :

Traduction
│
▼
Utilisateur active le slide
│
▼
Activation des options
│
├── Texte
├── Voix
└── Langue
11.1 Options
Texte

Slide permettant d'activer/désactiver la traduction du texte.

Texte     [ ON / OFF ]
Voix

Slide affiché mais désactivé pour la V1.

Voix      [ OFF ]

Il doit être possible de l'afficher dans l'interface afin de préparer les futures fonctionnalités, mais aucune génération vocale ne doit être déclenchée dans cette version.

Langue

Menu déroulant permettant de choisir la langue cible.

Exemple :

Langue
[ Français ▼ ]
12. Bouton Appliquer — Traduction

Ajouter :

Appliquer

Le bouton déclenche la traduction uniquement lorsque l'utilisateur le demande.

Exemple :

Traduction


Texte     [ ON ]
Voix      [ OFF ]


Langue
[ English ▼ ]


              [ Appliquer ]

Lorsque l'utilisateur clique sur Appliquer :

Transcript actuel
↓
Traduction IA
↓
Nouvelles lignes traduites
↓
Mise à jour de l'éditeur
↓
Mise à jour du preview

Le contenu traduit doit immédiatement être disponible dans l'éditeur pour permettre les modifications manuelles.

13. Conservation de la logique de traduction

La logique de traduction existante doit être conservée lorsqu'elle existe déjà.

Il faut éviter de recréer une deuxième implémentation de traduction.

Le système doit utiliser le pipeline IA existant :

TranslationService
│
├── Provider
├── Model
├── Token usage
├── Cost
└── Cache

La traduction doit également être compatible avec :

le système de crédits ;
le calcul du coût IA ;
le cache ;
le suivi des tokens ;
les quotas utilisateur.
14. Édition automatique des Reels

Le bouton :

Édition automatique

doit être entièrement revu.

Le clic ne doit plus lancer directement les traitements.

Il doit ouvrir un modal permettant à l'utilisateur de sélectionner les transformations souhaitées.

Principe UX central

Une fonctionnalité = un endroit pour la modifier.

Il ne doit plus y avoir deux systèmes concurrents permettant de modifier les captions.

Dans Vireel, « Sous-titres » devient le module unique de gestion du texte incrusté, aussi bien pour une vidéo complète que pour un Reel. Les Reels ajoutent ensuite leurs fonctionnalités propres : sélection des moments, cadrage, édition automatique, etc.