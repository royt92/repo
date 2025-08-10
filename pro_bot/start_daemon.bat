@echo off
echo ================================
echo   ТОРГОВЫЙ БОТ - DAEMON РЕЖИМ
echo ================================
echo.

REM Проверяем, что .env файл существует
if not exist .env (
    echo ❌ ОШИБКА: Файл .env не найден!
    echo Создайте файл .env с настройками API
    pause
    exit /b 1
)

echo ✅ Конфигурация найдена
echo 🚀 Запуск бота в daemon режиме...
echo 📊 Режим: paper trading (виртуальная торговля)
echo 💬 Уведомления будут отправляться в Telegram
echo.
echo ⚠️  Для остановки бота нажмите Ctrl+C
echo.

REM Запускаем бота в daemon режиме
py -m src.app daemon

REM Если произошла ошибка
if %errorlevel% neq 0 (
    echo.
    echo ❌ ОШИБКА: Бот завершился с ошибкой!
    echo Проверьте настройки в .env файле
    pause
    exit /b %errorlevel%
)

echo 🛑 Бот остановлен
pause

