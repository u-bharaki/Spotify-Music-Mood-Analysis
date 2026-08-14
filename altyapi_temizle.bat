@echo off
setlocal

echo.
echo =========================================================
echo VIBESTREAM ALTYAPISI YOK EDILIYOR (Nukleer Secenek)
echo =========================================================
echo.

:: 1. Adim: Helm Servislerini Temizle (Kibar Kapanis)
echo [ADIM 1/3] Veritabanlari (Postgres, Redis) hattan cikariliyor...
helm uninstall vibestream-postgres -n vibestream >nul 2>&1
helm uninstall vibestream-redis -n vibestream >nul 2>&1

:: 2. Adim: Butun Mahalleyi ve Diskleri (PVC) Havaya Ucur
echo [ADIM 2/3] 'vibestream' uzayi ve icindeki TUM diskler/podlar siliniyor...
echo (Bu islem verilerin buyuklugune gore 1-2 dakika surebilir lutfen bekleyin)
kubectl delete namespace vibestream

:: 3. Adim: Yikimin Tamamlanmasini Bekle
echo [ADIM 3/3] Enkaz kaldiriliyor, temizlik kontrolu yapiliyor...
:WAIT_NS_DELETE
kubectl get namespace vibestream >nul 2>&1
if %errorlevel% equ 0 (
    timeout /t 5 /nobreak >nul
    goto WAIT_NS_DELETE
)

echo.
echo =========================================================
echo [GOREV TAMAM] Sistem %100 temizlendi! Kubernetes su an bombos.
echo =========================================================
echo Yeniden calismak istediginde tek yapman gereken: altyapi_kur.bat
echo.
endlocal