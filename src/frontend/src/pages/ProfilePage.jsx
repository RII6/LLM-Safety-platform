import { useAuth } from '../context/AuthContext';

export default function ProfilePage() {
    const { user, isAuthenticated, logout } = useAuth();

    if (!isAuthenticated) {
        return (
            <div className="profile-page">
                <h2>Profile</h2>
                <p>You are not logged in.</p>
            </div>
        );
    }

    return (
        <div className="profile-page">
            <h2>Profile</h2>
            <p><strong>Username:</strong> {user.username}</p>
            <p><strong>Email:</strong> {user.email || 'Not set'}</p>
            <p><strong>Member since:</strong> {user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}</p>
            <button onClick={logout} className="logout-btn">Log out</button>
        </div>
    );
}