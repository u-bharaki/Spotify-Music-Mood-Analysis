@echo off
setlocal

:: Disaridan girilen 1. parametreyi (soft/hard) degiskene atiyoruz
set BUILD_MODE=%~1

echo.
echo =========================================================
echo VIBESTREAM ALTYAPISI HAZIRLANIYOR
echo =========================================================
echo.

:: Yonlendirmeleri bloksuz (parantezsiz) yapiyoruz ki CMD kafayi yemesin
if /I "%BUILD_MODE%"=="soft" goto SOFT_MODE
if /I "%BUILD_MODE%"=="hard" goto HARD_MODE

:: Eger parametre girilmediyse veya yanlis girildiyse sistem buraya duser
echo [HATA] Lutfen bir kurulum modu belirleyin usta!
echo.
echo KULLANIM SECENEKLERI:
echo   altyapi_kur.bat soft  -^> Mevcut JAR dosyasini kullanir (Hizli kurulum).
echo   altyapi_kur.bat hard  -^> Spark kodlarini SBT ile sifirdan derler (Yavas ama guncel).
echo.
exit /b 1


:HARD_MODE
echo [ADIM 0] 'hard' mod devrede: Spark Streaming JAR dosyasi sifirdan derleniyor...
cd "Spark Streaming"
:: Windows'ta baska bir komutu calistirirken scriptin kapanmamasi icin 'call' kullanilir
call sbt clean assembly

:: Hata kontrolu
if %errorlevel% neq 0 (
    echo.
    echo [HATA] SBT derlemesi patladi kanka! Kodlari veya build.sbt dosyasini kontrol et.
    cd ..
    exit /b %errorlevel%
)
cd ..
echo [BASARILI] Yeni fat-jar dosyasi kusursuz uretildi!
echo.
goto CONTINUE_SETUP


:SOFT_MODE
echo [ADIM 0] 'soft' mod devrede: Mevcut Spark JAR dosyasi kontrol ediliyor...
:: Compose dosyasinda belirtilen dizinde jar'in var olup olmadigina bakiyoruz
if not exist "Spark Streaming\target\scala-2.12\VibeStream-assembly-1.0.jar" (
    echo.
    echo [HATA] Kanka ortada hazir bir JAR yok! Derlemek icin once 'altyapi_kur.bat hard' komutunu calistirmalisin.
    echo.
    exit /b 1
)
echo [BASARILI] Hazir JAR dosyasi bulundu, derleme adimi atlandi! Zaman kazanildi.
echo.
goto CONTINUE_SETUP


:CONTINUE_SETUP
:: Buradan sonrasi standart K8s altyapi kurulum adimlarimiz
echo [ADIM 1/4] K8s'teki eski kalintilar temizleniyor...
kubectl delete namespace vibestream --ignore-not-found=true

echo Lutfen namespace silinene kadar bekleyin (Bazen 30-40 saniye surebilir)...
:WAIT_NS_DELETE
kubectl get namespace vibestream >nul 2>&1
if %errorlevel% equ 0 (
    timeout /t 5 /nobreak >nul
    goto WAIT_NS_DELETE
)

echo [ADIM 2/4] Yeni 'vibestream' alani (Namespace) olusturuluyor...
kubectl create namespace vibestream

echo [ADIM 3/4] DNS Yonlendirmeleri (Aliases) tanimlaniyor...
kubectl apply -f Yaml/aliases.yaml

echo [ADIM 4/4] Agir Abiler (Kafka, Postgres, Redis) sahneye cikiyor...
kubectl apply -f Yaml/kafka.yaml
helm install vibestream-postgres bitnami/postgresql -n vibestream --set auth.postgresPassword=vibe_password --set auth.username=vibe_admin --set auth.password=vibe_password --set auth.database=vibestream_db --set primary.persistence.enabled=false
helm install vibestream-redis bitnami/redis -n vibestream --set architecture=standalone --set auth.enabled=false --set master.resourcesPreset=none --set master.resources.limits.memory=256Mi

echo.
echo =========================================================
echo [BASARILI] Altyapi %BUILD_MODE% modu ile sorunsuz hazirlandi!
echo =========================================================
echo Podlarin durumunu izlemek icin:
echo kubectl get pods -n vibestream -w
echo.
endlocal