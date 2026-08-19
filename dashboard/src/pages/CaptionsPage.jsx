import GeneratedMediaPage from "../components/GeneratedMediaPage";
import { useTranslation } from "../state/LanguageContext";

export default function CaptionsPage() {
    const { t } = useTranslation();
    return (
        <GeneratedMediaPage
            title={t("mediaInput.captions_title")}
            subtitle={t("mediaInput.captions_subtitle")}
            createRoute="/dashboard/caption-generator?new=1"
            listEndpoint="/api/ia-captions"
            mediaUrlEndpoint="/api/ia-captions"
            deleteEndpoint="/api/ia-captions"
            shareEndpoint="/api/ia-captions"
            sharePlatforms={["tiktok", "youtube", "linkedin", "facebook","instagram"]}
            emptyLabel={t("mediaInput.captions_emptyLabel")}
        />
    );
}

