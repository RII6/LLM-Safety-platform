import React from "react";
import { NavLink, useNavigate } from "react-router-dom";

const Sidebar = ({ isOpen, onClose, isAuthenticated, onLogout }) => {
    const navigate = useNavigate();

    const handleLogout = () => {
        onLogout();
        onClose();
    };

    const handleLoginClick = () => {
        onClose();
        navigate("/");
    };

    return (
        <div className={`sidebar ${isOpen ? "open" : ""}`}>
            <div className="sidebar-header">
                <h2>Меню</h2>
                <button className="sidebar-close" onClick={onClose}>×</button>
            </div>
            <nav className="sidebar-nav">
                <ul>
                    <li>
                        <NavLink
                            to="/"
                            end
                            className={({ isActive }) => (isActive ? "active" : "")}
                            onClick={onClose}
                        >
                            Main page
                        </NavLink>
                    </li>

                    {isAuthenticated && (
                        <li>
                            <NavLink
                                to="/profile"
                                className={({ isActive }) => (isActive ? "active" : "")}
                                onClick={onClose}
                            >
                                Profile
                            </NavLink>
                        </li>
                    )}

                    <li>
                        <NavLink
                            to="/history"
                            className={({ isActive }) => (isActive ? "active" : "")}
                            onClick={onClose}
                        >
                            Recent Scans
                        </NavLink>
                    </li>

                    {isAuthenticated ? (
                        <li onClick={handleLogout}>
                            Log out
                        </li>
                    ) : (
                        <li onClick={handleLoginClick}>
                            Sign in/sign up
                        </li>
                    )}
                </ul>
            </nav>
        </div>
    );
};

export default Sidebar;