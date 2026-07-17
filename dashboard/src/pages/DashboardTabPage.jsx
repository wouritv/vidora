import PropTypes from "prop-types";
import App from "../App";

export default function DashboardTabPage({ tabKey }) {
    return <App activeTab={tabKey} />;
}

DashboardTabPage.propTypes = {
    tabKey: PropTypes.string.isRequired,
};