import GeneratedMediaPage from "../components/GeneratedMediaPage";

export default function YouTubeResumePage() {
    return (
        <GeneratedMediaPage
            title="IA Captions générés"
            subtitle="Retrouve tes vidéos avec captions IA, adaptés à la plateforme cible, partageables et téléchargeables."
            createRoute="/dashboard/youtube-studio?new=1"
            listEndpoint="/api/ia-captions"
            mediaUrlEndpoint="/api/ia-captions"
            deleteEndpoint="/api/ia-captions"
            shareEndpoint="/api/ia-captions"
            sharePlatforms={["tiktok", "youtube", "linkedin", "facebook"]}
            emptyLabel="Aucune vidéo IA captions trouvée."
        />
    );
}

