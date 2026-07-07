import React from 'react';

const Header = ({ toggleMenu, isAuthenticated }) => {
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
                <div className="user-profile">
                    <span className="user-icon">👤</span>
                    {isAuthenticated ? "User" : "Guest"}
                </div>
            </div>
        </header>
    );
};

export default Header;