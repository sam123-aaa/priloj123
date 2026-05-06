# Maintenance Mobile

Новый мобильный клиент без Kivy. Интерфейс сделан на нативных HTML-полях и кнопках, поэтому ввод текста и нажатия работают как в обычном мобильном приложении.

## Локальный запуск

```powershell
cd "D:\куцебо апи\PythonProject1\clients\mobile_app"
python -m http.server 3000
```

Открыть: `http://127.0.0.1:3000`

## APK

```powershell
cd "D:\куцебо апи\PythonProject1\clients\mobile_app"
.\build-apk.ps1
```

APK будет в `MaintenanceMobile-debug.apk`.

Клиент собран как нативная Android WebView-обёртка без Kivy и без npm. HTML/CSS/JS лежат в `android_native\app\src\main\assets`.
