import React from 'react';
import { useAuth } from '../context/AuthContext';

const Header = ({ toggleMenu }) => {
    const { user, isAuthenticated } = useAuth();

    return (
        <header>
            <div className="header-top">
                <div className="header-left">
                    <button className="menu-button" onClick={toggleMenu}>☰</button>
                    <div className="logo-area">
                        <span className="logo-icon">🛡️</span>
                        <h1>Unified LLM Safety Platform</h1>
                    </div>
                </div>
            </div>
        </header>
    );
};

export default Header;