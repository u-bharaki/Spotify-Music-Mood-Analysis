@echo off
setlocal enabledelayedexpansion

set TARGET=%~1

echo.
echo =========================================================
echo VIBESTREAM SERVIS BASLATICISI
echo =========================================================
echo.

if /I "%TARGET%"=="workers" goto WORKERS
if /I "%TARGET%"=="spark" goto SPARK
if /I "%TARGET%"=="superset" goto SUPERSET
if /I "%TARGET%"=="all" goto ALL

echo [HATA] Lutfen gecerli bir servis adi girin (workers, spark, superset, all).
exit /b 1

:: ---------------------------------------------------------
:: ALL (PARALEL BASLATMA MODU)
:: ---------------------------------------------------------
:ALL
set "TMP_DIR=%TEMP%\vibestream_deploy_%RANDOM%"
mkdir "%TMP_DIR%" >nul 2>&1

echo [BILGI] 3 servis arka planda paralel olarak baslatiliyor...
echo [LOGLAR] Detayli kayitlar: %TMP_DIR%
echo.

:: 3 servisi arka planda tetikle
start "" /b cmd /c ""%~f0" workers > "%TMP_DIR%\workers.log" 2>&1 & if not errorlevel 1 (echo OK > "%TMP_DIR%\workers.done") else (echo FAIL > "%TMP_DIR%\workers.done")"
start "" /b cmd /c ""%~f0" spark > "%TMP_DIR%\spark.log" 2>&1 & if not errorlevel 1 (echo OK > "%TMP_DIR%\spark.done") else (echo FAIL > "%TMP_DIR%\spark.done")"
start "" /b cmd /c ""%~f0" superset > "%TMP_DIR%\superset.log" 2>&1 & if not errorlevel 1 (echo OK > "%TMP_DIR%\superset.done") else (echo FAIL > "%TMP_DIR%\superset.done")"

set /a SECONDS=0
set "STATUS_W=DEVAM EDIYOR..."
set "STATUS_S=DEVAM EDIYOR..."
set "STATUS_SU=DEVAM EDIYOR..."

:POLL_LOOP
timeout /t 1 /nobreak >nul 2>&1
set /a SECONDS+=1

:: Durum kontrolleri
if exist "%TMP_DIR%\workers.done" (
    set /p RES_W=<"%TMP_DIR%\workers.done"
    if "!RES_W!"=="OK " (set "STATUS_W=[TAMAMLANDI]") else if "!RES_W!"=="OK" (set "STATUS_W=[TAMAMLANDI]") else (set "STATUS_W=[HATA ALDI]")
)
if exist "%TMP_DIR%\spark.done" (
    set /p RES_S=<"%TMP_DIR%\spark.done"
    if "!RES_S!"=="OK " (set "STATUS_S=[TAMAMLANDI]") else if "!RES_S!"=="OK" (set "STATUS_S=[TAMAMLANDI]") else (set "STATUS_S=[HATA ALDI]")
)
if exist "%TMP_DIR%\superset.done" (
    set /p RES_SU=<"%TMP_DIR%\superset.done"
    if "!RES_SU!"=="OK " (set "STATUS_SU=[TAMAMLANDI]") else if "!RES_SU!"=="OK" (set "STATUS_SU=[TAMAMLANDI]") else (set "STATUS_SU=[HATA ALDI]")
)

cls
echo =========================================================
echo VIBESTREAM PARALEL DAGITIM MERKEZI
echo =========================================================
echo Toplam Gecen Sure : !SECONDS! sn
echo.
echo  - Workers   : !STATUS_W!
echo  - Spark     : !STATUS_S!
echo  - Superset  : !STATUS_SU!
echo.
echo [LOG KLASORU] : %TMP_DIR%
echo =========================================================

if exist "%TMP_DIR%\workers.done" if exist "%TMP_DIR%\spark.done" if exist "%TMP_DIR%\superset.done" goto ALL_FINISHED

goto POLL_LOOP

:ALL_FINISHED
set "HAS_ERROR=0"

if exist "%TMP_DIR%\workers.done" (
    findstr /C:"FAIL" "%TMP_DIR%\workers.done" >nul && (
        set "HAS_ERROR=1"
        echo.
        echo =========================================================
        echo [HATA LOGU] WORKERS SERVISI
        echo =========================================================
        type "%TMP_DIR%\workers.log"
    )
)

if exist "%TMP_DIR%\spark.done" (
    findstr /C:"FAIL" "%TMP_DIR%\spark.done" >nul && (
        set "HAS_ERROR=1"
        echo.
        echo =========================================================
        echo [HATA LOGU] SPARK SERVISI
        echo =========================================================
        type "%TMP_DIR%\spark.log"
    )
)

if exist "%TMP_DIR%\superset.done" (
    findstr /C:"FAIL" "%TMP_DIR%\superset.done" >nul && (
        set "HAS_ERROR=1"
        echo.
        echo =========================================================
        echo [HATA LOGU] SUPERSET SERVISI
        echo =========================================================
        type "%TMP_DIR%\superset.log"
    )
)

if "!HAS_ERROR!"=="1" (
    echo.
    echo =========================================================
    echo [HATA] Bazi servisler basarisiz oldu! Yukaridaki loglari inceleyin.
    echo =========================================================
    endlocal
    exit /b 1
)

echo.
echo [BASARILI] Tum servis islemleri tamamlandi.
echo Podlari izlemek icin: kubectl get pods -n vibestream -w
echo.
endlocal
exit /b 0

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