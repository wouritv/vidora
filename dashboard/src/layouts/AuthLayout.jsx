import PropTypes from "prop-types";

export default function AuthLayout(props) {
    const { title, subtitle, children } = props;

    return (
        <div className="min-h-screen bg-zinc-950 text-zinc-100">
                {children}
        </div>
    );
}

AuthLayout.propTypes = {
    title: PropTypes.node.isRequired,
    subtitle: PropTypes.node,
    children: PropTypes.node.isRequired,
};
