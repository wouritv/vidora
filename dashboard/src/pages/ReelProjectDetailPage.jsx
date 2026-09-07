import { useParams } from "react-router-dom";
import ReelsPage from "./ReelsPage";

export default function ReelProjectDetailPage() {
    const { projectId } = useParams();
    return <ReelsPage projectId={projectId || ""} />;
}

