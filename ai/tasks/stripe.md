### Gestion de paiements avec Stripe

## taches a faire

- Intégrer l'API Stripe pour gérer les paiements en ligne.
- Sur la page abonnement, lorsque l'on clique sur choisir pour un abonnement, rediriger vers la page de paiement Stripe.
- Créer un formulaire de paiement sécurisé avec les informations nécessaires (nom, email, carte bancaire).
- Implémenter la logique pour traiter les paiements et gérer les erreurs éventuelles.
- Mettre en place un système de confirmation de paiement et d'envoi de reçus par email.
- quand un paiement est confirme dans stripe, faire l'insertion dans la table souscription de la base de données pour enregistrer l'abonnement de l'utilisateur. (id, created_at, userid, abonnement, payment_mode, payment_amount, payment_reference, payment_start_date, payment_end_date, payment_status, payment_comment)
- chaque abonnnement est pour une duree de 1 mois, donc le payment_start_date est la date du paiement et le payment_end_date est la date du paiement + 1 mois.
- utiliser le fichier .env pour stocker les clés API Stripe et autres informations sensibles.
- utiliser le fichier supabase_request.py pour faire les requetes vers la base de données supabase.

