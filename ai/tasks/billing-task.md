## TACHES A FAIRE
- Rattacher la souscription, notamment la logique de webhook apres insertion de la souscription, les modifications suivantes : 
  - Si le user a deja une entree dans la table user_data(id, created_at, user_id, update_at, credit, stockage) alors mettre a jours les champs credit et stockage en incrementant les valeurs existantes avec celles de la nouvelle souscription.
  - La table abonnement a des champs credit et stockage, c'est eux qui doivent etre recuperer et incrementer dans la table user_data.
  - Si le user n'a pas d'entree dans la table user_data, alors creer une nouvelle entree avec les valeurs de credit et stockage de la souscription.
  - Rajouter aussi une entree dans la table user_data_history avec les champs id, created_at, user_id, credit, storage, operation (input ou output, dans ce cas input), operation_type (reels, captions, subscription; dans ce cas subscription), operation_id (l'id de l'operation) pour garder un historique des modifications de credit et stockage.
- Pour les operations de generations de reels, de modification de reels (auto edit, subtitles, viral hook, post), de publication des posts sur les reseaux sociaux, de generation de captions, il faut integrer la logique de debit de credit
- Avant d'initier une operation (reel, caption, publications, etc), il faut verifier que le user a assez de credit pour effectuer l'operation. la verification se fait dans la table user_data, il faut que la valeur du credit soit superieur a 0, sinon il faut griser les boutons d'actions et mettre un warning a l'utilisateur qu'il n'a pas assez de credit pour effectuer l'operation.
- Pour les operations de generation de reels, de modification de reels (auto edit, subtitles, viral hook, post), de publication des posts sur les reseaux sociaux, de generation de captions, il faudrait definir une variable cous estimatif qui sera calcule selon la base ci-dessous 

- Pour les operations qui vont necessite Amazon S3, voici les variables d'environnements qui ont le prix par operation en USD, si une de ses operations doit etre facturée, il faudra multiplier le nombre d'operations par le prix correspondant.

AMAZON_S3_GO_PRICE=0.023
AMAZON_S3_PUT_REQUEST_PRICE=0.005
AMAZON_S3_COPY_REQUEST_PRICE=0.005
AMAZON_S3_GET_REQUEST_PRICE=0.0004
AMAZON_S3_DELETE_REQUEST_PRICE=0.0004
AMAZON_S3_POST_REQUEST_PRICE=0.005
AMAZON_S3_LIST_REQUEST_PRICE=0.0004

- Le taux de convertion credit/USD car l'utilisateur paie ses abonnements en USD, mais la facturation se fait en credit. Il faudra donc convertir le montant en USD en credit pour l'afficher dans la facture : CREDIT_UNIT_PRICE_BY_DOLLAR=100

- Si l'operation necessite de telecharger une video sur Youtube, il faudra integrer la facturation DATAIMPUILSE en considerant cette variable qui est le prix par Go en USD : DATA_IMPULSE_PRICE_BY_GO=1

- Le temps de traitement d'une operation est facturé en fonction du temps d'execution de l'operation. Il faudra donc integrer le prix par minute en USD : VIREEL_VPS_PRICE_BY_MINUTE=0.01

- pour les operations qui vont utiliser Assembly, OpenIA ou Gemini, il faudra integrer les prix par operation en USD pour chaque service par minute. Voici les variables d'environnements correspondantes :
  ASSEMBLY_ESTIMATE_COST_PER_MINUTE=0.21
  OPEN_IA_ESTIMATE_COST_PER_MINUTE=0.15
  GEMINI_ESTIMATE_COST_PER_MINUTE=0.25

- Avec ses elements au debut de l'operation, il faudra valider le prix total de l'operation en USD, puis le convertir en credit et s'assurer que le user a assez de credit, sinon il faudra refuser l'operation et afficher un message d'erreur indiquant que le user n'a pas assez de credit pour effectuer l'operation.

- Si un user dispose d'assez de credit, il faut faire l'operation, par contre il faudra obtenir pour chaque plateforme (Amazon S3, DataImpulse, Virel VPS, Assembly, OpenIA, Gemini) si possible le montant reellement consomme, le convertir en credit. Il faudra donc integrer un systeme de suivi de consommation pour chaque plateforme afin de calculer le montant reellement consomme par l'utilisateur.

- Pour chaque operation, il faudra remplir la table user_data_history avec les champs id, created_at, user_id, credit, storage, operation (input ou output, dans ce cas output), operation_type (reels, captions, subscription; dans ce cas reels, captions ou publications), operation_id (l'id de l'operation) pour garder un historique des modifications de credit et stockage.

- utiliser la variable VIREEL_PRICE_MAJORATION=2.0 pour majorer le prix de l'operation en credit pour les operations reels, captions et publications. Le prix final de l'operation sera donc le prix total de l'operation en credit multiplié par la variable VIREEL_PRICE_MAJORATION.
- pour chaque operation, il faudrait mettre a jour la table user_data avec les nouvelles valeurs de credit et stockage apres l'operation. Il faudra donc recuperer les valeurs actuelles de credit et stockage, les decrementer avec les valeurs de l'operation, puis mettre a jour la table user_data avec les nouvelles valeurs.

- il faudrait aussi stocker dans les tables jobs ou job_logs les informations sur l'operation, le prix total de l'operation en credit, le prix total de l'operation en USD, le montant reellement consomme par chaque plateforme (Amazon S3, DataImpulse, Virel VPS, Assembly, OpenIA, Gemini) en credit et en USD.

    public.jobs (
    id uuid primary key default gen_random_uuid(),
    status text not null default 'created',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_type text not null,
    attempts integer not null default 0,
    max_attempts integer not null default 2,
    progress integer not null default 0,
    current_step text,
    error_code text,
    error_message text,
    queue_name text not null default 'main',
    pipeline_name text,
    reserved_quota numeric(12, 4) not null default 0,
    consumed_quota numeric(12, 4) not null default 0,
    estimated_cost_usd numeric(12, 6) not null default 0,
    actual_cost_usd numeric(12, 6) not null default 0,
    job_data jsonb not null default '{}'::jsonb,
    result_data jsonb not null default '{}'::jsonb
    );
    
    public.job_logs (
    id bigserial primary key,
    job_id uuid not null references public.jobs(id) on delete cascade,
    level text not null default 'INFO',
    message text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
    );

- Sur la page settings, il faudrait afficher le credit et le stockage restant de l'utilisateur, ainsi que l'historique des operations avec les informations sur le type d'operation, le prix total de l'operation en credit et en USD, le montant reellement consomme par chaque plateforme (Amazon S3, DataImpulse, Virel VPS, Assembly, OpenIA, Gemini) en credit et en USD.
- L'utilisateur dois pouvoir racheter du credit supplementaires, selon la base de calcul suivant : CREDIT_UNIT_PRICE_BY_DOLLAR=100 (1 USD = 100 credit). Il faudra donc integrer un systeme de paiement pour permettre a l'utilisateur de racheter du credit supplementaire. Rajouter le mecanisme et l'interface pour que l'utilisateur puisse racheter du credit supplementaire. Il faudra aussi mettre a jour la table user_data avec les nouvelles valeurs de credit apres l'achat de credit supplementaire. Il faudra aussi rajouter une entree dans la table user_data_history avec les champs id, created_at, user_id, credit, storage, operation (input ou output, dans ce cas input), operation_type (reels, captions, subscription; dans ce cas subscription), operation_id (l'id de l'operation) pour garder un historique des modifications de credit et stockage.