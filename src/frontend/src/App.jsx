import { useState } from "react";
import { Routes, Route, useNavigate, Navigate } from "react-router-dom";
import "./App.css";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import HomePage from "./pages/HomePage";
import ProfilePage from "./pages/ProfilePage";
import HistoryPage from "./pages/HistoryPage";
import ComparePage from "./pages/ComparePage";


function App() {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const navigate = useNavigate();

    const handleLogin = () => {
        setIsAuthenticated(true);
        navigate("/profile");
    };

    const handleLogout = () => {
        setIsAuthenticated(false);
        navigate("/");
    };

    const toggleMenu = () => setIsMenuOpen((prev) => !prev);
    const closeMenu = () => setIsMenuOpen(false);

    return (
        <>
            <Header toggleMenu={toggleMenu} isAuthenticated={isAuthenticated} />
            <Sidebar
                isOpen={isMenuOpen}
                onClose={closeMenu}
                isAuthenticated={isAuthenticated}
                onLogout={handleLogout}
            />
            {isMenuOpen && <div className="sidebar-overlay" onClick={closeMenu}></div>}
            <main className={`main-content ${isMenuOpen ? "shifted" : ""}`}>
                <Routes>
                    <Route path="/" element={<HomePage />} />
                    <Route
                        path="/profile"
                        element={
                            isAuthenticated ? (
                                <ProfilePage isAuthenticated={isAuthenticated} onLogin={handleLogin} />
                            ) : (
                                <Navigate to="/" replace />
                            )
                        }
                    />
                    <Route path="/history" element={<HistoryPage />} />
                    <Route path="/compare/:id1/:id2" element={<ComparePage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </main>
        </>
    );
}

export default App;