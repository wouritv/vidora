## Objectif

Introduire la notion de **Projet** dans Vireel afin de regrouper les éléments générés lors d'une même opération, tout en conservant au maximum l'interface et les fonctionnalités existantes des pages **Reels** et **Sous-titres**.

Le changement doit être principalement organisationnel : les listes actuelles restent en place, mais chaque élément représente désormais un **projet** contenant les contenus générés.

### 1. Table `projects`

Créer une table `projects` :

* `id` : UUID, clé primaire
* `user_id` : UUID, clé étrangère vers `users`
* `name` : string
* `description` : text, optionnel
* `project_type` : enum `reel | caption`
* `source_type` : enum `upload | youtube | url`
* `source_url` : URL source originale, optionnelle
* `source_s3_key` : clé de la vidéo source stockée sur S3
* `source_duration` : durée de la vidéo source
* `source_size` : taille de la vidéo source
* `thumbnail_url` : URL de la miniature
* `output_count` : nombre de contenus générés
* `status` : enum `processing | completed | failed | cancelled`
* `created_at`
* `updated_at`
* `completed_at`

Ajouter `project_id` dans les tables `reels` et `captions`. Chaque contenu généré doit obligatoirement appartenir à un projet.

### 2. Gestion de la vidéo source

**Toute vidéo source d'un projet doit être stockée sur Amazon S3**, quelle que soit son origine.

* Upload utilisateur : la vidéo est envoyée sur S3.
* YouTube : la vidéo est téléchargée par Vireel puis stockée sur S3.
* Autre URL : la vidéo est téléchargée puis stockée sur S3.

La source originale peut être YouTube ou une autre URL, mais la vidéo utilisée par Vireel pour le traitement est toujours celle stockée sur S3.

La base de données ne doit pas stocker une URL S3 permanente comme lien d'accès à la vidéo. `source_s3_key` identifie l'objet S3 et Vireel génère une **URL pré-signée dynamique** lorsque la vidéo doit être consultée ou téléchargée.

La vidéo source doit rester inchangée pendant toute la durée de vie du projet.

### 3. Gestion de l'espace utilisateur

La taille de la vidéo source doit être **comptabilisée dans l'espace de stockage disponible du profil utilisateur**, en utilisant le mécanisme de gestion du stockage actuellement utilisé par Vireel.

Lors de la création d'un projet :

**espace utilisé = espace actuel + taille de la vidéo source**

L'opération doit vérifier que l'utilisateur dispose de suffisamment d'espace avant de stocker la source.

Les fichiers générés par le projet doivent également être comptabilisés conformément au mécanisme de stockage actuel de Vireel.

Lorsqu'un Reel, un Caption ou un projet est supprimé, les fichiers correspondants doivent être supprimés de S3 et l'espace occupé doit être immédiatement déduit du stockage utilisé par l'utilisateur.

La suppression d'un projet doit supprimer :

* la vidéo source ;
* les Reels/Captions générés ;
* les fichiers intermédiaires ou associés au projet devant être conservés sur S3.

L'espace libéré doit être réattribué au quota disponible de l'utilisateur selon le mécanisme actuel.

### 4. Création et traitement d'un projet

Lorsqu'un utilisateur démarre une opération Reel ou Sous-titres à partir d'une vidéo uploadée ou d'une URL YouTube, Vireel crée immédiatement un projet avec le statut `processing`.

La vidéo source est stockée sur S3 avant le traitement. Sa taille est enregistrée et imputée au stockage utilisateur.

La miniature est générée à partir de la vidéo source et les informations disponibles sont enregistrées dans le projet. Tous les résultats produits pendant l'opération sont associés à ce projet.

Le projet conserve son statut jusqu'à la fin de l'opération :

* `processing` : génération en cours
* `completed` : génération terminée avec succès
* `failed` : génération terminée avec une erreur
* `cancelled` : génération annulée

### 5. Comportement au clic selon le statut

**Projet `processing` :** cliquer sur le projet ouvre la page de génération avec le statut évolutif, la progression et les informations disponibles sur l'opération.

**Projet `completed` :** cliquer sur le projet affiche le résultat final.

* Projet Reel : afficher tous les Reels générés.
* Projet Caption : ouvrir directement l'éditeur de sous-titres existant.

**Projet `failed` :** cliquer sur le projet affiche la page de résultat avec l'état d'erreur et les informations disponibles sur l'échec.

### 6. Pages Reels et Sous-titres

Conserver la structure actuelle des pages sous forme de **liste** afin de limiter les changements UI.

Les filtres existants sont conservés :

* titre / recherche ;
* statut ;
* date de création.

La liste représente désormais les projets correspondant au type de la page.

Colonnes :

* miniature ;
* nom / titre du projet ;
* description ;
* nombre de contenus ;
* durée de la source ;
* statut ;
* date de création ;
* actions.

### 7. Actions

Les actions existantes doivent être conservées :

* **Play / Éditer**
* **Partager**
* **Télécharger**
* **Supprimer**

Ajouter un menu `...` au niveau du projet :

* Renommer le projet
* Supprimer le projet

Toute suppression doit obligatoirement demander une confirmation.

La suppression d'un Reel ou d'un Caption supprime uniquement son contenu et les fichiers S3 associés.

La suppression d'un projet supprime la totalité de ses contenus, sa vidéo source et les fichiers S3 associés, puis libère l'espace correspondant sur le compte utilisateur.

### 8. Résultat d'un projet Reel

Lorsqu'un projet Reel terminé est ouvert, afficher les Reels générés dans la logique actuelle.

Chaque Reel conserve :

* preview vidéo ;
* bouton Play ;
* titre ;
* description ;
* durée ;
* statut ;
* score de véracité ;
* actions existantes : éditer, partager, télécharger, supprimer.

Ajouter dans `reels` :

`truthfulness_score` : valeur de 0 à 100 déterminée par OpenAI lors de l'analyse de la transcription.

L'éditeur Reel actuel doit être conservé et réutilisé.

### 9. Résultat d'un projet Caption

Un projet Sous-titres correspond normalement à une seule vidéo traitée.

Lorsqu'un projet Caption est terminé, cliquer dessus ouvre directement l'éditeur de sous-titres existant, sans écran intermédiaire.

Les fonctionnalités et actions actuelles de l'éditeur doivent rester inchangées.

### 10. Édition

Modifier un Reel ou un Caption ne modifie jamais la source originale.

Toute modification met à jour `updated_at` du projet.

Les nouvelles versions/rendus générés doivent être associés au projet et leur espace S3 doit être comptabilisé selon le mécanisme actuel de gestion du stockage.

### 11. Principe d'architecture

La relation globale est :

**Project → Source S3 → Job/Processing → Generated Content → S3**

Le projet représente l'opération utilisateur, le Job représente le traitement technique et les Reels/Captions représentent les résultats.

Cette structure doit permettre d'ajouter ultérieurement d'autres types de contenus ou traitements sans remettre en cause le système de projets.
