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