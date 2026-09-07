import { useMemo } from "react";
import { useLocation, useParams } from "react-router-dom";
import CaptionsPage from "./CaptionsPage";

export default function CaptionProjectDetailPage() {
    const { projectId } = useParams();
    const location = useLocation();

    const autoOpenFirst = useMemo(() => {
        const params = new URLSearchParams(location.search || "");
        return params.get("autoplay") === "1";
    }, [location.search]);

    return <CaptionsPage projectId={projectId || ""} autoOpenFirst={autoOpenFirst} />;
}

