@echo off
echo Запуск торгового бота (одиночный запуск)...
echo.

REM Проверяем, что .env файл существует
if not exist .env (
    echo ОШИБКА: Файл .env не найден!
    echo Создайте файл .env с настройками API
    pause
    exit /b 1
)

REM Запускаем бота один раз
echo Запуск бота в режиме "once"...
py -m src.app once

REM Если произошла ошибка
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА: Бот завершился с ошибкой!
    echo Проверьте настройки в .env файле
    pause
    exit /b %errorlevel%
)

echo Бот завершил работу успешно
pause

