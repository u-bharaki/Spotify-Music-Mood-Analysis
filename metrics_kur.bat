@echo off
echo =========================================================
echo KUBERNETES METRICS SERVER KURULUMU
echo =========================================================
echo.

echo [ADIM 1] Metrics Server resmi paketi indiriliyor ve kuruluyor...
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

echo.
echo [ADIM 2] Insecure TLS yamasi (Docker Desktop/Yerel ortam icin) uygulaniyor...
kubectl patch -n kube-system deployment metrics-server --type=json -p="[{\"op\": \"add\", \"path\": \"/spec/template/spec/containers/0/args/-\", \"value\": \"--kubelet-insecure-tls\"}]"

echo.
echo =========================================================
echo [BASARILI] Kurulum tamamlandi!
echo Metrics podunun uyanip veri toplamaya baslamasi 30-60 saniye surebilir.
echo =========================================================
echo.
pause