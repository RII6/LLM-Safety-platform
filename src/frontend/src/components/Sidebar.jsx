import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Sidebar = ({ isOpen, onClose }) => {
    const { isAuthenticated, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        onClose();
        navigate('/');
    };

    const handleLoginClick = () => {
        onClose();
        navigate('/login');
    };

    return (
        <div className={`sidebar ${isOpen ? 'open' : ''}`}>
            <div className="sidebar-header">
            </div>
            <nav className="sidebar-nav">
                <ul>
                    <li>
                        <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')} onClick={onClose}>
                            Main page
                        </NavLink>
                    </li>
                    <li>
                        <NavLink to="/history" className={({ isActive }) => (isActive ? 'active' : '')} onClick={onClose}>
                            Recent Scans
                        </NavLink>
                    </li>
                    {isAuthenticated && (
                        <li>
                            <NavLink to="/profile" className={({ isActive }) => (isActive ? 'active' : '')} onClick={onClose}>
                                Profile
                            </NavLink>
                        </li>
                    )}
                    {isAuthenticated ? (
                        <li className="nav-action" onClick={handleLogout}>
                            Log out
                        </li>
                    ) : (
                        <li className="nav-action" onClick={handleLoginClick}>
                            Sign in / Sign up
                        </li>
                    )}
                </ul>
            </nav>
        </div>
    );
};

export default Sidebar;