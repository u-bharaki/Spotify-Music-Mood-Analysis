"""
VibeStream - Superset login-siz açılış konfigürasyonu.

Ne yapar:
  1. Her istekte, kullanıcı login olmamışsa otomatik olarak "admin" kullanıcısı
     ile login eder (login ekranı hiç görünmez).
  2. Ana sayfaya ("/") gelen istekleri otomatik olarak VibeStream dashboard'una
     yönlendirir, böylece Superset açılır açılmaz direkt panel görünür.

NOT: Bu sadece yerel/eğitim ortamı için uygundur (herkes admin olarak
giriş yapmış olur, gerçek bir kimlik doğrulama yoktur). Production'da
KESİNLİKLE kullanılmamalıdır.
"""

from flask import redirect, request
from flask_login import login_user, current_user

# provision_superset.py'deki DASHBOARD_SLUG ile AYNI olmalı.
VIBESTREAM_DASHBOARD_SLUG = "vibestream-mood"


def VIBESTREAM_AUTO_LOGIN_AND_REDIRECT(app):
    @app.before_request
    def _vibestream_auto_login():
        if not current_user or not current_user.is_authenticated:
            sm = app.appbuilder.sm
            admin_user = sm.find_user(username="admin")
            if admin_user:
                login_user(admin_user, remember=False)

    @app.before_request
    def _vibestream_redirect_root():
        if request.path in ("/", "/login/", "/superset/welcome/"):
            return redirect(f"/superset/dashboard/{VIBESTREAM_DASHBOARD_SLUG}/")


FLASK_APP_MUTATOR = VIBESTREAM_AUTO_LOGIN_AND_REDIRECT
PUBLIC_ROLE_LIKE = "Admin"

# ---------------------------------------------------------------------------
# VIBESTREAM MODERN TEMA
# ---------------------------------------------------------------------------
# Superset'in tüm arayüzünü (navbar, butonlar, menüler, formlar, koyu mod)
# Ant Design token sistemi üzerinden yeniden markalıyoruz. Bu, sadece
# dashboard içeriğini değil TÜM Superset kabuğunu (chrome) etkiler.
APP_NAME = "VibeStream"

THEME_OVERRIDES = {
    "borderRadius": 10,
    "fontFamily": "'Poppins', 'Inter', -apple-system, sans-serif",
    "colors": {
        "primary": {
            "base": "#1DB954",       # Spotify yeşili - marka rengi
            "dark1": "#169c46",
            "dark2": "#0f7a37",
            "light1": "#4CDE7C",
            "light2": "#B7F5CB",
        },
        "grayscale": {
            "base": "#8b8b8b",
            "dark1": "#1a1a1a",
            "dark2": "#121212",
            "light1": "#e8e8e8",
            "light2": "#f4f4f4",
        },
        "info": {"base": "#3A7BFF"},
        "success": {"base": "#1DB954"},
        "warning": {"base": "#FFB020"},
        "error": {"base": "#FF4D5E"},
    },
}

# Uygulama her açıldığında koyu mod ile başlasın (kullanıcı yine de
# navbar'daki anahtar ile açık moda geçebilir).
THEME_DEFAULT = {**THEME_OVERRIDES}
THEME_DARK = {
    **THEME_OVERRIDES,
    "algorithm": "dark",
    "colors": {
        **THEME_OVERRIDES["colors"],
        "grayscale": {
            "base": "#8b8b8b",
            "dark1": "#f4f4f4",
            "dark2": "#ffffff",
            "light1": "#1a1a1a",
            "light2": "#121212",
        },
    },
}