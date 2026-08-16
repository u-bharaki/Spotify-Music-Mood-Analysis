@echo off
setlocal

set TARGET=%~1

echo.
echo =========================================================
echo VIBESTREAM SERVIS BASLATICISI
echo =========================================================
echo.

if /I "%TARGET%"=="workers" goto WORKERS
if /I "%TARGET%"=="spark" goto SPARK
if /I "%TARGET%"=="superset" goto SUPERSET

echo [HATA] Lutfen gecerli bir servis adi girin (workers, spark, superset).
exit /b 1

:: ---------------------------------------------------------
:: SERVIS TANIMLAMALARI
:: ---------------------------------------------------------
:WORKERS
set DOCKERFILE_PATH=Docker/Dockerfile.workers
set IMAGE_NAME=vibestream-workers:latest
set YAML_PATH=Yaml/data-workers.yaml
goto RUN_DEPLOY

:SPARK
set DOCKERFILE_PATH=Docker/Dockerfile.spark
set IMAGE_NAME=vibestream-spark:latest
set YAML_PATH=Yaml/spark.yaml
goto RUN_DEPLOY

:SUPERSET
set YAML_PATH=Yaml/superset.yaml

echo [ADIM 1A] Superset Ana Imaji Derleniyor...
docker build -t vibestream-superset:v2 -f Docker/Dockerfile.superset .
if %errorlevel% neq 0 (
    echo [HATA] Superset Ana Imaji derlenemedi! Islem iptal edildi.
    exit /b %errorlevel%
)

echo [ADIM 1B] Superset Init Imaji Derleniyor...
docker build -t vibestream-superset-init:v2 -f Docker/Dockerfile.superset-init .
if %errorlevel% neq 0 (
    echo [HATA] Superset Init Imaji derlenemedi! Islem iptal edildi.
    exit /b %errorlevel%
)
goto JUST_DEPLOY

:: ---------------------------------------------------------
:: ORTAK MOTORLAR
:: ---------------------------------------------------------
:RUN_DEPLOY
echo [ADIM 1] '%TARGET%' icin Docker Imaji Derleniyor...
docker build -t %IMAGE_NAME% -f %DOCKERFILE_PATH% .
if %errorlevel% neq 0 (
    echo [HATA] Docker derlemesi patladi! Islem iptal edildi.
    exit /b %errorlevel%
)
goto JUST_DEPLOY

:JUST_DEPLOY
echo.
echo [ADIM 2] Kubernetes Ortamina Yukleniyor...
kubectl delete -f %YAML_PATH% --ignore-not-found=true
kubectl apply -f %YAML_PATH%

if %errorlevel% neq 0 (
    echo [HATA] K8s yuklemesi sirasinda hata olustu!
    exit /b %errorlevel%
)

echo.
echo =========================================================
echo [BASARILI] '%TARGET%' servisi sahaya suruldu!
echo =========================================================
echo Podlari izlemek icin: kubectl get pods -n vibestream -w
echo.
endlocal
exit /b 0