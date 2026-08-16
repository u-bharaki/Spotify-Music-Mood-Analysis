@echo off
setlocal

:: Girilen parametreyi al (soft veya hard)
set MODE=%~1

echo.
echo =========================================================
echo VIBESTREAM ALTYAPI TEMIZLEYICI
echo =========================================================
echo.

:: Parametre kontrolu
if /I "%MODE%"=="soft" goto SOFT_CLEAN
if /I "%MODE%"=="hard" goto HARD_CLEAN

:: Eger yanlis parametre girilirse veya bos birakilirsa uyar
echo [HATA] Lutfen bir temizlik modu secin!
echo.
echo KULLANIM:
echo   altyapi_temizle.bat soft  -^> Gecici durdurma: Uygulamalari kapatir ama VERILERI (PVC) korur.
echo   altyapi_temizle.bat hard  -^> NUKLEER SECENEK: Veriler dahil her seyi (PVC, DB) yok eder.
echo.
exit /b 1

:: ---------------------------------------------------------
:: 1. SOFT MOD (Veri Dostu Temizlik)
:: ---------------------------------------------------------
:SOFT_CLEAN
echo [SOFT MOD] Veriler ve kalici diskler (PVC) korunarak uygulamalar durduruluyor...
echo.

:: Tum calisan uygulamalari, gorevleri ve servisleri siler ama disklere (PVC) dokunmaz
echo - Superset kalintilari ve diger gorevler (Jobs) temizleniyor...
kubectl delete job --all -n vibestream >nul 2>&1

echo - Uygulamalar (Deployments ve StatefulSets) hattan cikariliyor...
kubectl delete deployment --all -n vibestream >nul 2>&1
kubectl delete statefulset --all -n vibestream >nul 2>&1

echo - Ag baglantilari (Services) kesiliyor...
kubectl delete service --all -n vibestream >nul 2>&1

echo.
echo =========================================================
echo [GOREV TAMAM] Podlar kapatildi, veriler (Postgres/Redis) guvende!
echo Yeniden baslatmak icin 'baslat.bat' kullanabilirsin.
echo =========================================================
goto END


:: ---------------------------------------------------------
:: 2. HARD MOD (Nukleer Yikim)
:: ---------------------------------------------------------
:HARD_CLEAN
echo [HARD MOD] NUKLEER YIKIM BASLADI! (Tum veriler ve diskler YOK edilecek)
echo.

:: Eski helm paketleri varsa kalintilari temizle
echo [ADIM 1/3] Varsa Helm kalintilari temizleniyor...
helm uninstall vibestream-postgres -n vibestream >nul 2>&1
helm uninstall vibestream-redis -n vibestream >nul 2>&1

:: Mahalleyi tamamen sil (Bu islem PVC dahil her seyi yok eder)
echo [ADIM 2/3] 'vibestream' uzayi ve icindeki TUM diskler/podlar siliniyor...
echo (Bu islem verilerin buyuklugune gore 1-2 dakika surebilir, lutfen bekleyin)
kubectl delete namespace vibestream

:: Yikimin tamamlanmasini bekle
echo [ADIM 3/3] Enkaz kaldiriliyor ve dogrulama yapiliyor...
:WAIT_NS_DELETE
kubectl get namespace vibestream >nul 2>&1
if %errorlevel% equ 0 (
    timeout /t 5 /nobreak >nul
    goto WAIT_NS_DELETE
)

:: Baslat.bat'in hata vermemesi icin bos mahalleyi tekrar olustur
echo - Yeni kurulumlar icin tertemiz 'vibestream' mahallesi aciliyor...
kubectl create namespace vibestream >nul 2>&1

echo.
echo =========================================================
echo [GOREV TAMAM] Sistem %100 sifirlandi! Kubernetes su an bombos.
echo Hatalardan arinmis bir sekilde 'baslat.bat' ile her seyi kurabilirsin.
echo =========================================================
goto END

:END
endlocal
exit /b 0