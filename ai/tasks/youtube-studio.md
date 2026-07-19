# Generation du resume d'une video

Il faut s'appuyer sur le formulaire youtube studio et la logique youtube studio et customiser

## Reste a faire
- le formulaire dois permettre d'uploader une video local uniquement
- le systeme va generer un resume de la video en se basant sur les inputs user, et les proposer a l'utilisateur
- Ajouter une page ou sont lister tous les resumes generes sous forme de tableau
- Les resumes generes doivent etre stockes sur supabase pour pouvoir les retrouver facilement
- analyser les ia utiliser par ia providers short et voir dans quelle mesure les remplacer par openIa, gemini, assemblyai
- proposer la bonne architecture de table a  (youtube_resume) dans supabase pour la gestion des resumes generes
- on dois sauvegarder les resumes generes dans la table supabase avec les champs suivants :
    - id
    - resume_url
    - resume_thumbnail_url
    - resume_title
    - resume_description
    - resume_duration
    - resume_created_at
    - resume_updated_at
    - resume_user_id
    - resume_status (en cours, termine, echec)
- on dois aussi sauvegarder les inputs pour la generation du resume
- Ajouter un systeme de recherche et de filtrage pour retrouver les resumes generes
- Ajouter un systeme de suppression des resumes generes
- Ajouter un systeme de partage des resumes generes sur les reseaux sociaux
- Ajouter un systeme de telechargement des resumes generes
- Ajouter un systeme de notification pour informer l'utilisateur lorsque le resume est genere
- conserver le mecanisme actuel et le mettre dans la page demarrer une action
- en cliquant sur le sidebar du dashboard on dois tomber sur la page qui liste tous les resumes generes
- Ajouter un systeme de pagination pour les resumes generes
- sauvegarder les resumes generes sur amazon s3 pour pouvoir les retrouver facilement
- chaque resume dois durer au moins 45 secondes, de plus dans le tableau qui liste les resumes generes action une action visualisation pour visualiser le resume
- pour la visualisation des videos qui sont sur s3, il faudrait penser a generer les liens signes dynamique pour mettre le telechargement la lecture ou le partage en tout temps, pour la previsualisation il daudrait que la popup ait une orientation comme les reels, aussi les videos sources qui ont servit pour les operations doivent etre supprimees a la fin des operations