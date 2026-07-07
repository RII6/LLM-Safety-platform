export default function ProfilePage({ isAuthenticated, onLogin }) {
    return (
        <div className="profile-page">
            <h2>Профиль пользователя</h2>
            {isAuthenticated ? (
                <div>
                    <p>Вы вошли как <strong>User</strong></p>
                    <p>Здесь будет информация о ваших сканах, настройках и т.д.</p>
                </div>
            ) : (
                <div>
                    <p>Вы не авторизованы.</p>
                    <button onClick={onLogin} className="login-btn">Войти</button>
                </div>
            )}
        </div>
    );
}