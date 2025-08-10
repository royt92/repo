#!/usr/bin/env python3
"""Скрипт для анализа работы торгового бота"""

import sqlite3
import json
from datetime import datetime, timedelta
import os

def analyze_database():
    """Анализ базы данных бота"""
    if not os.path.exists('bot_state.sqlite3'):
        print("❌ База данных не найдена!")
        return
    
    try:
        conn = sqlite3.connect('bot_state.sqlite3')
        cursor = conn.cursor()
        
        # Список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"📊 Таблицы в БД: {[t[0] for t in tables]}")
        
        # Анализ ордеров
        cursor.execute("SELECT COUNT(*) FROM orders")
        orders_count = cursor.fetchone()[0]
        print(f"📋 Всего ордеров: {orders_count}")
        
        if orders_count > 0:
            cursor.execute("SELECT * FROM orders ORDER BY time DESC LIMIT 5")
            recent_orders = cursor.fetchall()
            print("\n🕒 Последние ордера:")
            for order in recent_orders:
                print(f"  {order}")
        
        # Анализ сделок
        cursor.execute("SELECT COUNT(*) FROM trades")
        trades_count = cursor.fetchone()[0]
        print(f"\n💰 Всего сделок: {trades_count}")
        
        if trades_count > 0:
            cursor.execute("SELECT * FROM trades ORDER BY time DESC LIMIT 5")
            recent_trades = cursor.fetchall()
            print("\n💸 Последние сделки:")
            for trade in recent_trades:
                print(f"  {trade}")
            
            # PnL статистика
            cursor.execute("SELECT SUM(pnl), AVG(pnl), COUNT(*) FROM trades WHERE pnl > 0")
            win_stats = cursor.fetchone()
            cursor.execute("SELECT SUM(pnl), AVG(pnl), COUNT(*) FROM trades WHERE pnl < 0")
            loss_stats = cursor.fetchone()
            
            if win_stats[2] > 0 or loss_stats[2] > 0:
                total_pnl = (win_stats[0] or 0) + (loss_stats[0] or 0)
                win_rate = win_stats[2] / (win_stats[2] + loss_stats[2]) * 100
                print(f"\n📈 СТАТИСТИКА:")
                print(f"  💚 Прибыльных: {win_stats[2]} (${win_stats[0]:.2f})")
                print(f"  🔴 Убыточных: {loss_stats[2]} (${loss_stats[0]:.2f})")
                print(f"  🎯 Винрейт: {win_rate:.1f}%")
                print(f"  💰 Общий PnL: ${total_pnl:.2f}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка анализа БД: {e}")

def analyze_logs():
    """Анализ логов"""
    log_file = "logs/bot.log"
    if not os.path.exists(log_file):
        print("❌ Файл логов не найден!")
        return
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"\n📄 Анализ логов ({len(lines)} строк):")
        
        # Подсчет ошибок
        error_count = sum(1 for line in lines if '"levelname": "ERROR"' in line)
        warning_count = sum(1 for line in lines if '"levelname": "WARNING"' in line)
        
        print(f"  ❌ Ошибки: {error_count}")
        print(f"  ⚠️ Предупреждения: {warning_count}")
        
        # Анализ символов с ошибками
        error_symbols = {}
        for line in lines:
            if 'screener_symbol_error' in line:
                try:
                    log_data = json.loads(line.strip())
                    symbol = log_data.get('symbol', 'unknown')
                    error_symbols[symbol] = error_symbols.get(symbol, 0) + 1
                except:
                    pass
        
        if error_symbols:
            print(f"\n🔍 Символы с ошибками скринера:")
            for symbol, count in sorted(error_symbols.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {symbol}: {count} ошибок")
        
        # Последние записи
        print(f"\n📋 Последние 3 записи:")
        for line in lines[-3:]:
            try:
                log_data = json.loads(line.strip())
                timestamp = log_data.get('asctime', 'unknown')
                level = log_data.get('levelname', 'INFO')
                message = log_data.get('message', 'no message')
                print(f"  [{timestamp}] {level}: {message}")
            except:
                print(f"  {line.strip()}")
                
    except Exception as e:
        print(f"❌ Ошибка анализа логов: {e}")

def check_bot_status():
    """Проверка статуса бота"""
    print("🤖 АНАЛИЗ ТОРГОВОГО БОТА")
    print("=" * 50)
    
    # Проверка процессов
    import subprocess
    try:
        result = subprocess.run(['tasklist'], capture_output=True, text=True, shell=True)
        python_processes = [line for line in result.stdout.split('\n') if 'python.exe' in line.lower()]
        print(f"🔄 Python процессов: {len(python_processes)}")
        for proc in python_processes:
            if proc.strip():
                print(f"  {proc.strip()}")
    except:
        print("❌ Не удалось проверить процессы")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    check_bot_status()
    analyze_database()
    analyze_logs()
    
    print("\n" + "=" * 50)
    print("✅ Анализ завершен!")



