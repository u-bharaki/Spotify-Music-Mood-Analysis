@echo off
setlocal

echo.
echo =========================================================
echo VIBESTREAM ALTYAPISI HAZIRLANIYOR (Temizlik ve Kurulum)
echo =========================================================
echo.

:: 1. Adim: Eski Kalintilari Temizle
echo [ADIM 1/4] Mevcut kurulumlar temizleniyor...
kubectl delete namespace vibestream --ignore-not-found=true

:: Namespace silinene kadar bekle (Bu islem biraz surebilir)
echo Lutfen namespace silinene kadar bekleyin (Bazen 30-40 saniye surebilir)...
:WAIT_NS_DELETE
kubectl get namespace vibestream >nul 2>&1
if %errorlevel% equ 0 (
    timeout /t 5 /nobreak >nul
    goto WAIT_NS_DELETE
)

:: 2. Adim: Yepyeni Bir Alan (Namespace) Olustur
echo [ADIM 2/4] Yeni 'vibestream' alani (Namespace) olusturuluyor...
kubectl create namespace vibestream

:: 3. Adim: Yönlendirmeleri (Aliases) Kur
echo [ADIM 3/4] DNS Yonlendirmeleri (Aliases) tanimlaniyor...
kubectl apply -f Yaml/aliases.yaml

:: 4. Adim: Agir Abileri (Kafka, Postgres, Redis) Ayaga Kaldir
echo [ADIM 4/4] Agir Abiler (Kafka, Postgres, Redis) sahneye cikiyor...

:: Kafka
kubectl apply -f Yaml/kafka.yaml

:: Postgres (Helm ile)
helm install vibestream-postgres bitnami/postgresql -n vibestream --set auth.postgresPassword=postgres --set auth.database=spotify_mood --set primary.persistence.enabled=false

:: Redis (Helm ile - optimize edilmis 256MB RAM ile)
helm install vibestream-redis bitnami/redis -n vibestream --set architecture=standalone --set auth.enabled=false --set master.resourcesPreset=none --set master.resources.limits.memory=256Mi

echo.
echo =========================================================
echo [BASARILI] Altyapi hazir! Veritabanlari ve Kafka kalkisa gecti.
echo =========================================================
echo Podlarin durumunu izlemek icin:
echo kubectl get pods -n vibestream -w
echo.
echo Podlar 'Running' olduktan sonra 'baslat.bat' ile Seeder/Simulator'u cagirabilirsin.
echo.
endlocal