# Generation de shorts IA via une description 

Il faut s'appuyer sur le formulaire ai shorts et la logique ai shorts et customiser

### Reste a faire
- pour generer un short IA, l'utilisateur va decrire son produit ou son business, choisir la langue et le ton de la video, puis cliquer sur generer
- le systeme va generer un short IA en se basant sur les inputs user, et les proposer a l'utilisateur 
- Ajouter une page ou sont lister tous les reels generes sous forme de tableau
- analyser les ia utiliser par ia providers short et voir dans quelle mesure les remplacer par openIa, gemini, assemblyai
- Les reels generes doivent etre stockes sur supabase pour pouvoir les retrouver facilement
- proposer la bonne architecture de table a  (ia_short) dans supabase pour la gestion des reels generes
- on dois sauvegarder les reels generes dans la table supabase avec les champs suivants :
    - id
    - reel_url
    - reel_thumbnail_url
    - reel_title
    - reel_description
    - reel_duration
    - reel_created_at
    - reel_updated_at
    - reel_user_id
    - reel_status (en cours, termine, echec)
- on dois aussi sauvegarder les inputs pour la generation du reel
- Ajouter un systeme de recherche et de filtrage pour retrouver les reels generes
- Ajouter un systeme de suppression des reels generes
- Ajouter un systeme de partage des reels generes sur les reseaux sociaux
- Ajouter un systeme de telechargement des reels generes
- Ajouter un systeme de notification pour informer l'utilisateur lorsque le reel est genere
- conserver le mecanisme actuel et le mettre dans la page demarrer une action
- en cliquant sur le sidebar du dashboard on dois tomber sur la page qui liste tous les reels generes
- Ajouter un systeme de pagination pour les reels generes
- sauvegarder les reels generes sur amazon s3 pour pouvoir les retrouver facilement
- chaque reel dois durer au moins 20 secondes, de plus dans le tableau qui liste les reels generes action une action visualisation pour visualiser le reel
- pour la visualisation des videos qui sont sur s3, il faudrait penser a generer les liens signes dynamique pour mettre le telechargement la lecture ou le partage en tout temps, pour la previsualisation il daudrait que la popup ait une orientation comme les reels, aussi les videos sources qui ont servit pour les operations doivent etre supprimees a la fin des operations