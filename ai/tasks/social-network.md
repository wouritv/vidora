## Tache a faire
- Dans app.py j'ai rajoute des fonctions et des endpoints pour la gestion des reseaux sociaux. Il faut maintenant les tester pour s'assurer qu'ils fonctionnent correctement : connect, callback, fetch_platform_identity, get_valid_token, publish_post, upload_youtube_video, publish_to_tiktok, poll_tiktok_status, publish_tiktok_endpoint
- Valider que tout est correct et ajuster au besoin
- Faire le branchement dans Settings.jsx pour que les utilisateurs puissent se connecter à leurs comptes de réseaux sociaux et publier du contenu directement depuis l'application.
- Ajuster aussi les fonctions de partage social pour les reels et les captions au niveau de la publication en integrant les nouvelles fonctionnalités de publication sur les réseaux sociaux.
- Rendre aussi fonctionnelle la gestion de la publication programme et ajuster les tables supabases au besoin pour stocker les informations nécessaires à la publication programmée.
- pour le branchement UI des fonctions de publications, s'inspirer de ceci :
          async function connectPlatform(platform) {
          const res = await fetch(`/api/auth/${platform}/connect`);
          const { auth_url } = await res.json();
        
          const popup = window.open(auth_url, "oauth", "width=600,height=700");
        
          window.addEventListener("message", function handler(e) {
          if (e.data.type === "oauth_success") {
          refreshConnectedAccounts();
          window.removeEventListener("message", handler);
          }
          });
          }
        
      async function publishToSocials(platforms, content) {
      const results = await Promise.allSettled(
      platforms.map(platform =>
      fetch(`/api/publish/${platform}`, {
      method: "POST",
      body: JSON.stringify(content),
      headers: { "Content-Type": "application/json" }
      })
      )
      );
      return results; // gère les succès/échecs individuellement par plateforme
      }
  - Pour la gestion de la publication programmée, il faudra créer une interface utilisateur permettant aux utilisateurs de sélectionner une date et une heure pour la publication, ainsi que les plateformes sur lesquelles ils souhaitent publier. Ensuite, il faudra ajuster les fonctions backend pour gérer ces publications programmées, en utilisant des tâches planifiées (par exemple avec Celery ou un autre système de planification) pour exécuter les publications à l'heure spécifiée.
  - utiliser les tables supabases suivantes pour la gestion des publications : social_accounts : (id, created_at, user_id, platform, access_token_encrypted, refresh_token_encrypted, platform_user_id, platform_account_name, scopes), publish_jobs (id, created_at, user_id, platform, external_id, status, error_message, completed_at)  
  - les variables d'environnement suivants existe deja :
    FACEBOOK_CLIENT_ID=xxx
    FACEBOOK_CLIENT_SECRET=xxx
    LINKEDIN_CLIENT_ID=xxx
    LINKEDIN_CLIENT_SECRET=xxx
    YOUTUBE_CLIENT_ID=xxx
    YOUTUBE_CLIENT_SECRET=xxx
    TIKTOK_CLIENT_KEY=xxx
    TIKTOK_CLIENT_SECRET=xxx
    ENCRYPTION_KEY=xxx  # pour chiffrer les tokens en DB
    BASE_URL=https://tonapp.com
- Au besoin ajouter de nouvelles tables dans supabase pour gérer les publications programmées et les informations supplémentaires nécessaires pour chaque plateforme de réseau social.