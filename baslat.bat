@echo off
setlocal

:: Parametreleri degiskenlere atiyoruz
set DOCKERFILE_PATH=%~1
set IMAGE_NAME=%~2
set YAML_PATH=%~3

:: Eger parametre girilmediyse kullaniciya yardimci ol
if "%DOCKERFILE_PATH%"=="" (
    echo.
    echo ---------------------------------------------------------
    echo HATA: Eksik parametre girdiniz!
    echo.
    echo KULLANIMI: baslat.bat ^<Dockerfile-Yolu^> ^<Imaj-Adi^> ^<YAML-Yolu^>
    echo ORNEK: baslat.bat Dockerfile.workers vibestream-workers:latest Yaml/data-workers.yaml
    echo ---------------------------------------------------------
    echo.
    exit /b 1
)

echo.
echo =========================================================
echo [ADIM 1] Docker Imaji Derleniyor...
echo Hedef Dockerfile: %DOCKERFILE_PATH%
echo Olusturulacak Imaj: %IMAGE_NAME%
echo =========================================================
docker build -t %IMAGE_NAME% -f %DOCKERFILE_PATH% .

:: Eger build sirasinda hata olursa scripti durdur
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Docker derlemesi sirasinda bir sorun olustu! Islem iptal ediliyor.
    exit /b %errorlevel%
)

echo.
echo =========================================================
echo [ADIM 2] Kubernetes Ortamina Yukleniyor...
echo Hedef YAML: %YAML_PATH%
echo =========================================================
:: Kubernetes Job'lari (Seeder gibi) bazen inatci olur, once eski ayni isimli gorevleri silmeyi dener (hata verirse gormezden gelir)
kubectl delete -f %YAML_PATH% --ignore-not-found=true

:: Yeni imajla yaml dosyasini sisteme bas
kubectl apply -f %YAML_PATH%

if %errorlevel% neq 0 (
    echo.
    echo [HATA] Kubernetes'e manifesto uygulanirken bir sorun olustu!
    exit /b %errorlevel%
)

echo.
echo =========================================================
echo [BASARILI] Tum islemler sorunsuz tamamlandi kanka!
echo =========================================================
echo Podlarin son durumunu izlemek icin su komutu girebilirsin:
echo kubectl get pods -n vibestream -w
echo.
endlocal