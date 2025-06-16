import time
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
import json
import os

class SmartTradingBot:
    def __init__(self):
        # API ключи
        self.api_key = "NNuq2b3zxIRHtk7Ei7"
        self.secret_key = "1fK71fJ8bJNHZWzR1hXq1N9iKQqHGN3RsfoX"
        self.telegram_token = "7914279468:AAE0j5FC1Jm1mIzbicVtSCK8XWXzGozCVt8"
        self.telegram_chat_id = "389193169"
        
        # Подключение к API
        self.session = HTTP(
            testnet=False,
            api_key=self.api_key,
            api_secret=self.secret_key,
            recv_window=5000
        )
        
        # Торговые настройки
        self.leverage = 20
        self.base_risk = 0.04
        self.min_profit_close = 0.03
        self.stop_loss = 0.02
        self.take_profit = 0.08
        self.min_confidence = 0.4
        
        # Волатильные монеты
        self.coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT"]
        
        # Система обучения
        self.active_positions = {}
        self.trading_stats = {
            'total_trades': 0,
            'wins': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0
        }
        
        # Адаптивные параметры
        self.strategy_performance = {'momentum': 0.5, 'volume': 0.5, 'trend': 0.5}
        
        print("✅ Умный торговый бот инициализирован - РЕАЛЬНАЯ ТОРГОВЛЯ")
    
    def send_message(self, text):
        """Отправка в Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            requests.post(url, data={"chat_id": self.telegram_chat_id, "text": text}, timeout=10)
        except Exception as e:
            print(f"⚠️ Telegram ошибка: {e}")
    
    def get_balance(self):
        """Получение баланса"""
        try:
            result = self.session.get_wallet_balance(accountType="UNIFIED")
            if result['retCode'] == 0:
                for item in result['result']['list']:
                    for coin in item['coin']:
                        if coin['coin'] == 'USDT':
                            return float(coin['walletBalance'])
            return 0
        except Exception as e:
            print(f"⚠️ Ошибка получения баланса: {e}")
            return 0
    
    def get_market_data(self, symbol, interval="15", limit=50):
        """Получение рыночных данных"""
        try:
            result = self.session.get_kline(
                category="linear", 
                symbol=symbol, 
                interval=interval, 
                limit=limit
            )
            if result['retCode'] == 0:
                data = []
                for candle in result['result']['list']:
                    data.append({
                        'close': float(candle[4]),
                        'volume': float(candle[5]),
                        'high': float(candle[2]),
                        'low': float(candle[3])
                    })
                return pd.DataFrame(data[::-1])
            return None
        except Exception as e:
            print(f"❌ Ошибка данных {symbol}: {e}")
            return None
    
    def smart_analysis(self, symbol):
        """Умный анализ"""
        df = self.get_market_data(symbol)
        if df is None or len(df) < 20:
            return None
        
        signals = {}
        
        # 1. Анализ тренда
        sma_5 = df['close'].rolling(5).mean().iloc[-1]
        sma_15 = df['close'].rolling(15).mean().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        trend_score = 0
        if sma_5 > sma_15 and current_price > sma_5:
            trend_score = 0.7
        elif sma_5 < sma_15 and current_price < sma_5:
            trend_score = -0.7
        signals['trend'] = trend_score
        
        # 2. Анализ объемов
        avg_volume = df['volume'].rolling(10).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        volume_score = 0
        if volume_ratio > 1.2:
            volume_score = 0.6 if trend_score > 0 else -0.6
        signals['volume'] = volume_score
        
        # 3. Моментум анализ
        price_change = (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]
        momentum_score = 0
        if 0.003 < price_change < 0.05:
            momentum_score = 0.5
        elif -0.05 < price_change < -0.003:
            momentum_score = -0.5
        signals['momentum'] = momentum_score
        
        # Комбинированный сигнал
        final_score = 0
        for strategy, score in signals.items():
            weight = self.strategy_performance.get(strategy, 0.5)
            final_score += score * weight
        
        confidence = abs(final_score) / len(signals)
        signal = 'BUY' if final_score > 0.2 else 'SELL' if final_score < -0.2 else None
        
        return {
            'signal': signal,
            'confidence': confidence,
            'price': current_price,
            'components': signals
        }
    
    def calculate_position_size(self, confidence):
        """Расчет размера позиции"""
        balance = self.get_balance()
        risk_multiplier = 1 + (confidence - 0.5)
        adaptive_risk = self.base_risk * risk_multiplier
        adaptive_risk = max(0.02, min(adaptive_risk, 0.1))
        return balance * adaptive_risk * self.leverage
    
    def execute_trade(self, symbol, analysis):
        """🔥 РЕАЛЬНАЯ ТОРГОВЛЯ ВКЛЮЧЕНА"""
        try:
            signal = analysis['signal']
            confidence = analysis['confidence']
            current_price = analysis['price']
            
            print(f"🎯 Торговля {symbol}: {signal} с уверенностью {confidence:.2%}")
            
            if confidence < self.min_confidence:
                return False
            
            position_value = self.calculate_position_size(confidence)
            qty = round(position_value / current_price, 6)
            
            if qty < 0.001:
                print(f"❌ Размер позиции слишком мал: {qty}")
                return False
            
            side = "Buy" if signal == "BUY" else "Sell"
            
            print(f"📤 Размещаем РЕАЛЬНЫЙ ордер: {side} {qty} {symbol}")
            
            # 🔥 РЕАЛЬНАЯ ТОРГОВЛЯ
            result = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=str(qty)
            )
            
            print(f"📋 Результат ордера: {result}")
            
            if result['retCode'] == 0:
                # Расчет уровней
                if side == "Buy":
                    stop_loss = current_price * (1 - self.stop_loss)
                    take_profit = current_price * (1 + self.take_profit)
                else:
                    stop_loss = current_price * (1 + self.stop_loss)
                    take_profit = current_price * (1 - self.take_profit)
                
                # Сохраняем позицию
                order_id = result['result']['orderId']
                self.active_positions[order_id] = {
                    'symbol': symbol,
                    'side': side,
                    'size': qty,
                    'entry_price': current_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'timestamp': datetime.now(),
                    'components': analysis['components'],
                    'max_profit': 0
                }
                
                # Установка защитных ордеров
                try:
                    self.session.set_trading_stop(
                        category="linear",
                        symbol=symbol,
                        stopLoss=str(round(stop_loss, 4)),
                        takeProfit=str(round(take_profit, 4))
                    )
                except Exception as e:
                    print(f"⚠️ Ошибка установки стопов: {e}")
                
                self.trading_stats['total_trades'] += 1
                
                # Уведомление
                message = f"""🚀 ПОЗИЦИЯ ОТКРЫТА

📊 {symbol} {side}
💰 Размер: {qty}
💵 Цена: ${current_price:.4f}
🛡️ Stop Loss: ${stop_loss:.4f}
🎯 Take Profit: ${take_profit:.4f}
📈 Уверенность: {confidence:.1%}
💹 Плечо: {self.leverage}x"""
                
                self.send_message(message)
                print(f"✅ ПОЗИЦИЯ ОТКРЫТА: {symbol} {side}")
                return True
                
            else:
                error_msg = result.get('retMsg', 'Неизвестная ошибка')
                print(f"❌ Ошибка ордера: {error_msg}")
                self.send_message(f"❌ Ошибка открытия позиции {symbol}: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ Критическая ошибка торговли {symbol}: {e}")
            self.send_message(f"🚨 Критическая ошибка торговли {symbol}: {e}")
            return False
    
    def manage_positions(self):
        """Управление позициями"""
        if not self.active_positions:
            return
        
        print(f"📊 Управление {len(self.active_positions)} позициями...")
        
        for order_id, pos in list(self.active_positions.items()):
            try:
                symbol = pos['symbol']
                
                ticker = self.session.get_tickers(category="linear", symbol=symbol)
                if ticker['retCode'] != 0:
                    continue
                
                current_price = float(ticker['result']['list'][0]['lastPrice'])
                entry_price = pos['entry_price']
                side = pos['side']
                
                if side == "Buy":
                    pnl_percent = (current_price - entry_price) / entry_price
                else:
                    pnl_percent = (entry_price - current_price) / entry_price
                
                if pnl_percent > pos['max_profit']:
                    pos['max_profit'] = pnl_percent
                
                should_close = False
                reason = ""
                
                # Умные условия закрытия
                if pnl_percent >= self.min_profit_close:
                    current_analysis = self.smart_analysis(symbol)
                    if current_analysis:
                        if (side == "Buy" and current_analysis['signal'] == "SELL") or \
                           (side == "Sell" and current_analysis['signal'] == "BUY"):
                            should_close = True
                            reason = "Разворот сигнала"
                        elif current_analysis['confidence'] < 0.3:
                            should_close = True
                            reason = "Низкая уверенность"
                
                if pnl_percent >= 0.15:
                    should_close = True
                    reason = "Высокая прибыль 15%"
                
                if pos['max_profit'] > 0.08:
                    drawdown = pos['max_profit'] - pnl_percent
                    if drawdown > 0.02:
                        should_close = True
                        reason = "Трейлинг стоп"
                
                hold_time = datetime.now() - pos['timestamp']
                if hold_time > timedelta(hours=8) and pnl_percent > 0.02:
                    should_close = True
                    reason = "Тайм-стоп"
                
                print(f"  📊 {symbol}: P&L {pnl_percent:.2%}, Время {hold_time}")
                
                # Закрытие позиции
                if should_close:
                    print(f"🏁 Закрываем позицию {symbol}: {reason}")
                    
                    close_side = "Sell" if side == "Buy" else "Buy"
                    
                    result = self.session.place_order(
                        category="linear",
                        symbol=symbol,
                        side=close_side,
                        orderType="Market",
                        qty=str(pos['size']),
                        reduceOnly=True
                    )
                    
                    if result['retCode'] == 0:
                        if pnl_percent > 0:
                            self.trading_stats['wins'] += 1
                        
                        self.trading_stats['total_pnl'] += pnl_percent
                        self.trading_stats['win_rate'] = (self.trading_stats['wins'] / self.trading_stats['total_trades']) * 100
                        
                        self.update_strategy_performance(pos, pnl_percent)
                        
                        # Уведомление
                        pnl_emoji = "🟢" if pnl_percent > 0 else "🔴"
                        message = f"""🏁 ПОЗИЦИЯ ЗАКРЫТА {pnl_emoji}

📊 {symbol} {side}
📈 P&L: {pnl_percent:.2%}
💰 Результат: ${pnl_percent * pos['size'] * entry_price:.2f}
🎯 Причина: {reason}
⏰ Время: {hold_time}"""
                        
                        self.send_message(message)
                        print(f"✅ ПОЗИЦИЯ ЗАКРЫТА: {symbol} {pnl_percent:.2%}")
                        
                        del self.active_positions[order_id]
                        
                    else:
                        print(f"❌ Ошибка закрытия {symbol}: {result.get('retMsg')}")
                        
            except Exception as e:
                print(f"⚠️ Ошибка управления позицией {symbol}: {e}")
                
    def update_strategy_performance(self, pos, pnl_percent):
        """Обновление производительности стратегий"""
        components = pos.get('components', {})
        
        for strategy, score in components.items():
            if strategy in self.strategy_performance:
                if pnl_percent > 0:
                    self.strategy_performance[strategy] = min(1.0, self.strategy_performance[strategy] + pnl_percent * 0.1)
                else:
                    self.strategy_performance[strategy] = max(0.1, self.strategy_performance[strategy] + pnl_percent * 0.05)
        
        print(f"🧠 Обновлена производительность: {self.strategy_performance}")
    
    def send_report(self):
        """Отправка отчета"""
        balance = self.get_balance()
        stats = self.trading_stats
        
        report = f"""📊 ОТЧЕТ ТОРГОВОГО БОТА

💰 Баланс: ${balance:.2f}
📈 Всего сделок: {stats['total_trades']}
✅ Прибыльных: {stats['wins']}
📊 Win Rate: {stats['win_rate']:.1f}%
💹 Общий P&L: {stats['total_pnl']:.2%}
🔄 Активных позиций: {len(self.active_positions)}

🧠 Производительность стратегий:
• Тренд: {self.strategy_performance['trend']:.1%}
• Объемы: {self.strategy_performance['volume']:.1%}  
• Моментум: {self.strategy_performance['momentum']:.1%}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        self.send_message(report)
    
    def run(self):
        """Основной цикл работы"""
        print("🚀 ЗАПУСК РЕАЛЬНОЙ ТОРГОВЛИ")
        
        balance = self.get_balance()
        if balance < 10:
            print("❌ Недостаточно средств (минимум $10)")
            return
        
        print(f"✅ Баланс: ${balance:.2f}")
        self.send_message(f"🤖 БОТ ЗАПУЩЕН - РЕАЛЬНАЯ ТОРГОВЛЯ!\n💰 Баланс: ${balance:.2f}\n🎯 Плечо: {self.leverage}x")
        
        cycle = 0
        last_report = datetime.now()
        
        try:
            while True:
                cycle += 1
                print(f"\n{'='*50}")
                print(f"🔄 ЦИКЛ #{cycle} - {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'='*50}")
                
                # Управление позициями
                self.manage_positions()
                
                # Поиск новых сигналов
                if len(self.active_positions) < 3:
                    print(f"\n🔍 ПОИСК СИГНАЛОВ ({len(self.active_positions)}/3 позиций)...")
                    
                    for coin in self.coins:
                        if any(pos['symbol'] == coin for pos in self.active_positions.values()):
                            continue
                        
                        analysis = self.smart_analysis(coin)
                        
                        if analysis and analysis['signal'] and analysis['confidence'] >= self.min_confidence:
                            print(f"🎯 СИГНАЛ {analysis['signal']} для {coin} ({analysis['confidence']:.1%})")
                            
                            success = self.execute_trade(coin, analysis)
                            if success:
                                time.sleep(5)
                        
                        time.sleep(2)
                else:
                    print("📊 Максимум позиций достигнут (3/3)")
                
                # Отчет каждые 2 часа
                if (datetime.now() - last_report).seconds > 7200:
                    self.send_report()
                    last_report = datetime.now()
                
                # Статистика
                balance = self.get_balance()
                print(f"\n💰 Баланс: ${balance:.2f}")
                print(f"📊 Позиций: {len(self.active_positions)}")
                print(f"📈 Сделок: {self.trading_stats['total_trades']}")
                print(f"✅ Win Rate: {self.trading_stats['win_rate']:.1f}%")
                
                print(f"\n😴 Пауза 90 секунд...")
                time.sleep(90)
                
        except KeyboardInterrupt:
            print("\n🛑 Остановка бота...")
            self.send_message("🛑 Бот остановлен пользователем")
            
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            self.send_message(f"🚨 Критическая ошибка: {e}")

# Запуск бота
if __name__ == "__main__":
    print("🔥 ВНИМАНИЕ: РЕАЛЬНАЯ ТОРГОВЛЯ АКТИВИРОВАНА!")
    print("💰 Убедитесь что у вас достаточно средств")
    print("⚠️ Торговля с плечом связана с рисками")
    
    confirm = input("\n✅ Подтвердите запуск реальной торговли (да/нет): ")
    
    if confirm.lower() in ['да', 'yes', 'y', '1']:
        try:
            bot = SmartTradingBot()
            balance = bot.get_balance()
            
            if balance > 0:
                print(f"✅ Подключение успешно! Баланс: ${balance:.2f}")
                bot.run()
            else:
                print("❌ Ошибка подключения к API")
                
        except Exception as e:
            print(f"❌ Ошибка запуска: {e}")
    else:
        print("❌ Запуск отменен")
