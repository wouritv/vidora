import GeneratedMediaPage from "../components/GeneratedMediaPage";

export default function AIShortsPage() {
    return (
        <GeneratedMediaPage
            title="AI Shorts générés"
            subtitle="Recherche, filtre, visualise, partage et télécharge tous tes shorts IA générés à partir de descriptions de produit ou business."
            createRoute="/dashboard/ai-shorts"
            listEndpoint="/api/ia-shorts"
            mediaUrlEndpoint="/api/ia-shorts"
            deleteEndpoint="/api/ia-shorts"
            shareEndpoint="/api/ia-shorts"
            emptyLabel="Aucun short IA trouvé."
        />
    );
}

