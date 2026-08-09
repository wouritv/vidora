## Tache a faire
- Ajuster la logique de traitements en fil d'attente pour améliorer la performance aussi bien pour les reels que pour les captions
- Au lieu d'utiliser jobs: Dict[str, Dict] = {} pour stocker les jobs, utiliser supabase pour sauvegarder les jobs dans une base de données. Cela permettra de mieux gérer les états des jobs et d'assurer la persistance des données. Creer une table "jobs" dans supabase avec les colonnes suivantes : id (UUID), status (string), created_at (timestamp), updated_at (timestamp), user_id (UUID), job_data (JSONB). Mettre à jour le code pour interagir avec cette table pour créer, mettre à jour et récupérer les jobs.
- Ajouter un système de notification pour informer les utilisateurs lorsque leur job est terminé ou en erreur. Cela peut être fait via email ou notifications push.
- Mettre en place un mécanisme de réessai automatique pour les jobs échoués afin d'améliorer la fiabilité du système.
- Centraliser la gestion des queues pour permettre une meilleure scalabilité et une gestion plus efficace des ressources. Cela avec des operations claires comme  create_job() , enqueue_job() , start_job() , update_progress(), complete_job() , fail_job(), cancel_job()
- Rendre le nombre de workers configurable pour permettre d'ajuster la charge de travail en fonction des besoins. il y a deja la gestion des jobs concurrents par worker mais il faut rendre le nombre de workers configurable via le fichier d'environnement.
- Structure les operations de traitements en regroupant dans des pipelines coherents avec ce qu'ils font. Par exemple, pour les reels, on peut avoir un pipeline ReelProcessingPipeline qui regroupe toutes les étapes nécessaires pour traiter un reel, et pour les captions, un pipeline CaptionProcessingPipeline. Cela permettra de mieux organiser le code et de faciliter la maintenance. (si des actions sont communes entre les deux pipelines, il est possible de créer une classe de base Pipeline qui contient les méthodes communes et que les deux pipelines héritent de cette classe)
- Normaliser les fichiers temporaires, si cela n'est pas encore fait, pour chaque operation creer un dossier temporaire unique pour stocker les fichiers temporaires et s'assurer qu'ils sont supprimés après utilisation. Cela permettra d'éviter les conflits de noms de fichiers et de mieux gérer l'espace disque. Prevoir un mecanisme de suppression automatique des fichiers temporaires après un certain temps la fin du traitement (15mn ou rendre configurable) ainsi que les jobs abandonnees.
- avant de basculer de assemblyIA vers faster-whisper, il faut d'assurer que le job assembly a bien failed et avoir fait au moins 1 a 2 essais de retry avant de basculer vers faster-whisper. Il faut aussi s'assurer que le job assembly a bien été mis à jour dans la base de données avec le status "failed" avant de lancer le job faster-whisper.
- organiser MediaPipe et Yolo, reserver Yolo pour les scenes complexe ou lorsque MediaPipe ne peut pas detecter correctement les objets. Il faut aussi s'assurer que les jobs MediaPipe sont bien mis à jour dans la base de données avec le status "failed" avant de lancer un job Yolo. MediaPipe doit être le premier choix pour les detections d'objets, et Yolo ne doit être utilisé que lorsque MediaPipe échoue ou ne peut pas détecter correctement les objets.
- Pour les jobs, penses aussi a stocker les logs dans la base de données pour pouvoir les consulter en cas de besoin. Cela permettra de mieux comprendre les erreurs et d'améliorer le système.
- Separer les types de job en definissant un catalogue de jobs avec des types bien définis (ex: TRANSCRIBE, GENERATE_SUBTITLES, TRANSLATE, DETECT_HIGHLIGHTS, GENERATE_REELS, GENERATE_HIGHLIGHT_VIDEO, RENDER_VIDEO, GENERATE_THUMBNAIL) et utiliser ces types pour gérer les jobs dans la base de données et dans le code. Cela permettra de mieux organiser les jobs et de faciliter la maintenance.
- Mettre en place un systeme de quotas afin de bien qualiber la consommation des ressources et d'éviter les abus.Ne fais pas :

utilisateur clique
→ quota consommé

Je recommande :

Job créé
↓
quota réservé
↓
traitement
↓
SUCCESS → quota consommé
FAILED → quota libéré
- Ajuste la logique de gestion de couts en ressortant peut etre en bd combien coute reellement chaque job pour pouvoir mieux gérer les quotas et les coûts associés à chaque type de job. Cela permettra d'avoir une meilleure visibilité sur la consommation des ressources et d'optimiser les coûts. par exemple : job
  ├── durée vidéo
  ├── durée traitement
  ├── CPU time
  ├── GPU time si disponible
  ├── transcription provider
  ├── modèle utilisé
  ├── tokens IA
  └── coût estimé
- il faudrait aussi des limites configurables pour les actions utilisateurs, par exemple : MAX_VIDEO_DURATION
  MAX_FILE_SIZE
  MAX_CONCURRENT_JOBS
  MAX_STORAGE_PER_USER
  MAX_JOBS_PER_MINUTE