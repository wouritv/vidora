### Objectif

Adapter uniquement l'interface utilisateur de Vireel pour introduire une organisation par **Projets**, sans casser les composants, actions ou éditeurs existants.

Le changement doit être **minimal et progressif** : conserver le design actuel, les listes, les boutons, les modals et les éditeurs existants autant que possible.

---

## 1. Navigation Sidebar

Modifier les entrées actuelles **Reels** et **Sous-titres** pour introduire une navigation à deux niveaux.

### Reels

```text
Reels
└── Mes projets
    ├── Projet A — 8 Reels
    ├── Projet B — 5 Reels
    └── Projet C — 12 Reels
```

Cliquer sur **Mes projets** affiche la liste des projets Reel.

Cliquer sur un projet ouvre son contenu :

```text
Reels
└── Projet A
    ├── Reel 1
    ├── Reel 2
    └── Reel 3
```

La page du projet doit réutiliser **la liste de Reels existante**, avec exactement les mêmes colonnes et actions que l'interface actuelle.

---

## 2. Page « Mes projets » — Reels

La page doit reprendre le composant de liste actuellement utilisé pour les Reels, mais les lignes représentent désormais des **projets**.

Conserver le même style visuel et les mêmes mécanismes de recherche/filtres.

Chaque projet doit afficher au minimum :

* Nom
* Description
* Nombre de Reels générés
* Durée de la vidéo source
* Statut
* Date de création
* Menu d'actions `...`

Actions du projet :

* Renommer
* Supprimer

La suppression doit obligatoirement afficher une modal de confirmation.

**Important : ne pas supprimer ou remplacer les actions existantes des Reels. Elles doivent simplement être déplacées au niveau du Reel lorsque l'utilisateur ouvre un projet.**

---

## 3. Page d'un projet Reel

Lorsqu'un utilisateur ouvre un projet Reel terminé, afficher les Reels appartenant à ce projet.

Réutiliser **le composant de liste Reel actuellement existant**.

Ne pas créer une nouvelle interface pour les Reels.

Conserver exactement les fonctionnalités actuelles :

* Play / Éditer
* Partager
* Télécharger
* Supprimer

Les colonnes actuelles doivent rester disponibles :

* Titre
* Description
* Durée
* Statut
* Date de création
* Actions

Le bouton Play doit continuer à ouvrir **le modal/éditeur Reel existant**.

La suppression d'un Reel doit conserver son comportement actuel, avec désormais une confirmation avant suppression.

---

## 4. Navigation Sous-titres

Pour les Sous-titres, appliquer le même principe de projet mais avec une UX plus directe car un projet Caption contient normalement un seul résultat.

```text
Sous-titres
└── Mes projets
    ├── Vidéo A
    ├── Vidéo B
    └── Vidéo C
```

La page **Mes projets** affiche la liste des projets de type `caption`.

Chaque ligne représente donc une opération de sous-titrage.

Afficher :

* Nom / titre
* Description
* Durée
* Statut
* Date de création
* Actions

Comme un projet Caption contient normalement une seule vidéo traitée, **ne pas créer une page intermédiaire inutile contenant une liste d'un seul élément**.

---

## 5. Clic sur un projet Caption

Lorsqu'un projet Caption est `completed`, cliquer sur le projet doit ouvrir directement **l'éditeur de sous-titres existant** avec le contenu généré.

Le comportement actuel de l'éditeur doit rester inchangé.

Les actions existantes doivent également rester disponibles :

* Play / Éditer
* Partager
* Télécharger
* Supprimer

---

## 6. Gestion des projets en cours

Le statut du projet doit déterminer la destination lors du clic.

### Projet `processing`

Ne pas afficher le résultat final.

Le clic doit ouvrir **la page de génération actuellement utilisée par Vireel**, avec :

* progression
* étape actuelle
* statut évolutif
* informations disponibles sur le traitement

Il faut réutiliser la page/composant de génération existant et ne pas créer un nouveau système de génération.

### Projet `completed`

Le clic affiche le résultat final :

* Reel → liste des Reels générés dans le projet
* Caption → ouverture directe de l'éditeur Caption

### Projet `failed`

Le clic ouvre la page de génération/résultat avec :

* statut `failed`
* message d'erreur
* informations disponibles sur ce qui s'est passé
* possibilité de revenir à la liste des projets

Ne pas afficher un faux résultat lorsqu'une opération a échoué.

---

## 7. Principe UX à respecter

L'arborescence finale doit être :

```text
SIDEBAR
│
├── Reels
│   │
│   └── Mes projets
│       ├── Projet A — 8 Reels
│       ├── Projet B — 5 Reels
│       └── Projet C — 12 Reels
│
│       └── Projet A
│           ├── Reel 1
│           ├── Reel 2
│           └── Reel 3
│
└── Sous-titres
    │
    └── Mes projets
        ├── Vidéo A
        ├── Vidéo B
        └── Vidéo C
              │
              └── clic
                   ↓
              Éditeur Sous-titres
```

**Le projet est donc une couche organisationnelle supplémentaire, pas une refonte des écrans existants.**

---

## 8. Règles importantes

1. Ne pas refaire les éditeurs Reel ou Sous-titres.
2. Ne pas supprimer les actions existantes.
3. Ne pas remplacer la liste actuelle des Reels par une grille.
4. Ne pas créer une page supplémentaire inutile pour les Captions.
5. Réutiliser les composants UI existants autant que possible.
6. Les filtres existants doivent continuer à fonctionner.
7. Les actions Play, Éditer, Partager, Télécharger et Supprimer doivent conserver leur logique actuelle.
8. Ajouter une confirmation avant toute suppression.
9. La navigation doit clairement distinguer **Projets** et **contenus générés**.
10. Le statut du projet contrôle ce que l'utilisateur voit lorsqu'il clique dessus.
11. Un projet en cours mène à la génération.
12. Un projet terminé mène au résultat.
13. Un projet en erreur mène au détail de l'échec.
14. Ne pas introduire de changement visuel majeur en dehors de cette nouvelle organisation.

### Résultat attendu

L'utilisateur doit avoir l'impression que Vireel fonctionne comme aujourd'hui, mais que ses opérations sont désormais regroupées dans des projets :

**Mes projets → Projet → Contenus générés → Édition / Partage / Téléchargement / Suppression**

L'objectif principal est de **factoriser l'organisation sans casser l'expérience utilisateur existante**.
