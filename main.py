import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import pandas as pd
import os
from datetime import datetime
import random
import sqlite3
from io import BytesIO

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
user_sessions = {}
user_states = {}
user_data = {}

class MassSenderBot:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.bot = None
        
    async def start(self):
        """Запуск бота"""
        self.bot = TelegramClient('bot_session', api_id, api_hash).start(bot_token=self.bot_token)
        
        # Регистрация обработчиков
        self.register_handlers()
        
        print("🤖 Бот запущен!")
        await self.bot.run_until_disconnected()
    
    def register_handlers(self):
        """Регистрация обработчиков событий"""
        
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            """Обработчик команды /start"""
            user_id = event.sender_id
            user_states[user_id] = 'main_menu'
            
            await event.respond(
                "🤖 **Бот для массовой рассылки в Telegram**\n\n"
                "Доступные команды:\n"
                "/setup - Настройка аккаунта для рассылки\n"
                "/scrape - Сбор пользователей из чата/канала\n"
                "/draft - Создание черновика сообщения\n"
                "/send - Начать рассылку\n"
                "/stats - Статистика\n"
                "/help - Помощь"
            )
        
        @self.bot.on(events.NewMessage(pattern='/setup'))
        async def setup_handler(event):
            """Настройка аккаунта"""
            user_id = event.sender_id
            user_states[user_id] = 'awaiting_api_id'
            
            await event.respond(
                "🔧 **Настройка аккаунта для рассылки**\n\n"
                "Для начала введите ваш API ID (можно получить на https://my.telegram.org):"
            )
        
        @self.bot.on(events.NewMessage(pattern='/scrape'))
        async def scrape_handler(event):
            """Сбор пользователей"""
            user_id = event.sender_id
            
            if user_id not in user_sessions:
                await event.respond("❌ Сначала настройте аккаунт через /setup")
                return
            
            user_states[user_id] = 'awaiting_chat_link'
            await event.respond("🔗 Введите ссылку на чат/канал (например: t.me/username или https://t.me/username):")
        
        @self.bot.on(events.NewMessage(pattern='/draft'))
        async def draft_handler(event):
            """Создание черновика"""
            user_id = event.sender_id
            user_states[user_id] = 'awaiting_draft'
            
            await event.respond(
                "📝 **Создание черновика**\n\n"
                "Введите текст сообщения для рассылки:\n\n"
                "Поддерживается форматирование:\n"
                "**жирный** - жирный текст\n"
                "__курсив__ - курсив\n"
                "`код` - моноширинный текст\n"
                "[текст](ссылка) - гиперссылка"
            )
        
        @self.bot.on(events.NewMessage(pattern='/send'))
        async def send_handler(event):
            """Начало рассылки"""
            user_id = event.sender_id
            
            if user_id not in user_sessions:
                await event.respond("❌ Сначала настройте аккаунт через /setup")
                return
            
            if 'drafts' not in user_data.get(user_id, {}) or not user_data[user_id]['drafts']:
                await event.respond("❌ Сначала создайте черновик через /draft")
                return
            
            # Показываем список черновиков
            drafts = user_data[user_id]['drafts']
            message = "📋 **Выберите черновик для отправки:**\n\n"
            for i, draft in enumerate(drafts, 1):
                message += f"{i}. {draft[:50]}...\n"
            
            user_states[user_id] = 'awaiting_draft_selection'
            await event.respond(message)
        
        @self.bot.on(events.NewMessage(pattern='/stats'))
        async def stats_handler(event):
            """Статистика"""
            user_id = event.sender_id
            
            if user_id not in user_data:
                await event.respond("📊 Статистика будет доступна после начала работы")
                return
            
            user_info = user_data[user_id]
            db_file = f'users_{user_id}.csv'
            sent_file = f'sent_{user_id}.csv'
            
            total_users = 0
            sent_messages = 0
            
            if os.path.exists(db_file):
                df = pd.read_csv(db_file)
                total_users = len(df)
            
            if os.path.exists(sent_file):
                df = pd.read_csv(sent_file)
                sent_messages = len(df)
            
            await event.respond(
                f"📊 **Статистика:**\n\n"
                f"👥 Пользователей в базе: {total_users}\n"
                f"📤 Отправлено сообщений: {sent_messages}\n"
                f"📝 Черновиков: {len(user_info.get('drafts', []))}\n"
                f"🔧 Аккаунт настроен: {'✅' if user_id in user_sessions else '❌'}"
            )
        
        @self.bot.on(events.NewMessage(pattern='/help'))
        async def help_handler(event):
            """Помощь"""
            await event.respond(
                "🆘 **Помощь по боту:**\n\n"
                "1. /setup - Настройте свой аккаунт (API ID и Hash)\n"
                "2. /scrape - Соберите пользователей из чата\n"
                "3. /draft - Создайте сообщение для рассылки\n"
                "4. /send - Запустите рассылку\n\n"
                "⚠️ **Важно:**\n"
                "- Соблюдайте лимиты Telegram\n"
                "- Используйте аккаунт осторожно\n"
                "- Сохраняйте backup данных"
            )
        
        @self.bot.on(events.NewMessage)
        async def message_handler(event):
            """Обработчик всех сообщений"""
            user_id = event.sender_id
            text = event.text
            
            if user_id not in user_states:
                user_states[user_id] = 'main_menu'
                return
            
            state = user_states[user_id]
            
            try:
                if state == 'awaiting_api_id':
                    try:
                        api_id = int(text)
                        user_data[user_id] = {'api_id': api_id}
                        user_states[user_id] = 'awaiting_api_hash'
                        await event.respond("✅ API ID принят. Теперь введите API Hash:")
                    except ValueError:
                        await event.respond("❌ Неверный формат API ID. Введите число:")
                
                elif state == 'awaiting_api_hash':
                    user_data[user_id]['api_hash'] = text
                    user_states[user_id] = 'awaiting_phone'
                    await event.respond("✅ API Hash принят. Теперь введите номер телефона (в международном формате, например: +79991234567):")
                
                elif state == 'awaiting_phone':
                    user_data[user_id]['phone'] = text
                    
                    # Пытаемся создать клиент
                    try:
                        client = TelegramClient(
                            StringSession(), 
                            user_data[user_id]['api_id'], 
                            user_data[user_id]['api_hash']
                        )
                        
                        await client.connect()
                        
                        # Отправляем код верификации
                        sent_code = await client.send_code_request(user_data[user_id]['phone'])
                        user_data[user_id]['phone_code_hash'] = sent_code.phone_code_hash
                        user_sessions[user_id] = client
                        
                        user_states[user_id] = 'awaiting_code'
                        await event.respond("📲 Код верификации отправлен. Введите код из Telegram:")
                    
                    except Exception as e:
                        await event.respond(f"❌ Ошибка: {str(e)}")
                        user_states[user_id] = 'main_menu'
                
                elif state == 'awaiting_code':
                    try:
                        client = user_sessions[user_id]
                        
                        # Завершаем вход
                        await client.sign_in(
                            phone=user_data[user_id]['phone'],
                            code=text,
                            phone_code_hash=user_data[user_id]['phone_code_hash']
                        )
                        
                        user_states[user_id] = 'main_menu'
                        await event.respond("✅ Аккаунт успешно настроен! Теперь можете использовать /scrape, /draft, /send")
                    
                    except Exception as e:
                        await event.respond(f"❌ Ошибка входа: {str(e)}")
                        user_states[user_id] = 'main_menu'
                
                elif state == 'awaiting_chat_link':
                    # Сбор пользователей
                    await self.scrape_users(event, user_id, text)
                
                elif state == 'awaiting_draft':
                    if user_id not in user_data:
                        user_data[user_id] = {}
                    if 'drafts' not in user_data[user_id]:
                        user_data[user_id]['drafts'] = []
                    
                    user_data[user_id]['drafts'].append(text)
                    user_states[user_id] = 'main_menu'
                    await event.respond(f"✅ Черновик сохранен! Всего черновиков: {len(user_data[user_id]['drafts'])}")
                
                elif state == 'awaiting_draft_selection':
                    try:
                        draft_index = int(text) - 1
                        drafts = user_data[user_id]['drafts']
                        
                        if 0 <= draft_index < len(drafts):
                            selected_draft = drafts[draft_index]
                            user_data[user_id]['selected_draft'] = selected_draft
                            user_states[user_id] = 'confirm_sending'
                            
                            await event.respond(
                                f"📤 **Подтверждение рассылки**\n\n"
                                f"Сообщение: {selected_draft[:100]}...\n\n"
                                f"Продолжить? (да/нет)"
                            )
                        else:
                            await event.respond("❌ Неверный номер черновика")
                    
                    except ValueError:
                        await event.respond("❌ Введите номер черновика")
                
                elif state == 'confirm_sending':
                    if text.lower() in ['да', 'yes', 'y', 'д']:
                        await self.start_mass_sending(event, user_id)
                    else:
                        user_states[user_id] = 'main_menu'
                        await event.respond("❌ Рассылка отменена")
            
            except Exception as e:
                await event.respond(f"💥 Произошла ошибка: {str(e)}")
                user_states[user_id] = 'main_menu'
    
    async def scrape_users(self, event, user_id, chat_link):
        """Сбор пользователей из чата"""
        try:
            client = user_sessions[user_id]
            await event.respond("🔄 Начинаем сбор пользователей...")
            
            chat = await client.get_entity(chat_link)
            users_data = []
            
            async for user in client.iter_participants(chat, aggressive=True, limit=1000):
                if user.username and not user.bot:
                    users_data.append({
                        'user_id': user.id,
                        'username': user.username,
                        'first_name': user.first_name or '',
                        'last_name': user.last_name or '',
                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'source_chat': getattr(chat, 'title', 'Unknown')
                    })
            
            # Сохраняем в файл
            db_file = f'users_{user_id}.csv'
            df = pd.DataFrame(users_data)
            
            if os.path.exists(db_file):
                existing_df = pd.read_csv(db_file)
                combined_df = pd.concat([existing_df, df]).drop_duplicates(subset=['user_id'])
                combined_df.to_csv(db_file, index=False)
                new_users = len(combined_df) - len(existing_df)
            else:
                df.to_csv(db_file, index=False)
                new_users = len(df)
            
            user_states[user_id] = 'main_menu'
            await event.respond(f"✅ Сбор завершен! Добавлено {new_users} новых пользователей. Всего в базе: {len(pd.read_csv(db_file))}")
        
        except Exception as e:
            await event.respond(f"❌ Ошибка при сборе пользователей: {str(e)}")
            user_states[user_id] = 'main_menu'
    
    async def start_mass_sending(self, event, user_id):
        """Запуск массовой рассылки"""
        try:
            client = user_sessions[user_id]
            message_text = user_data[user_id]['selected_draft']
            db_file = f'users_{user_id}.csv'
            sent_file = f'sent_{user_id}.csv'
            
            if not os.path.exists(db_file):
                await event.respond("❌ База пользователей не найдена")
                return
            
            df = pd.read_csv(db_file)
            
            # Фильтруем уже отправленных
            if os.path.exists(sent_file):
                sent_df = pd.read_csv(sent_file)
                sent_user_ids = set(sent_df['user_id'].tolist())
                users_to_send = df[~df['user_id'].isin(sent_user_ids)]
            else:
                users_to_send = df
                sent_user_ids = set()
            
            total_to_send = len(users_to_send)
            
            if total_to_send == 0:
                await event.respond("❌ Нет новых пользователей для отправки")
                return
            
            await event.respond(f"🚀 Начинаем рассылку для {total_to_send} пользователей...")
            
            success_count = 0
            failed_count = 0
            sent_history = []
            
            for index, row in users_to_send.iterrows():
                username = row['username']
                
                try:
                    result = await client.send_message(username, message_text)
                    
                    if result:
                        success_count += 1
                        sent_history.append({
                            'user_id': row['user_id'],
                            'username': username,
                            'sent_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'message': message_text[:100]
                        })
                        
                        # Отправляем лог в чат
                        if success_count % 10 == 0:  # Каждые 10 успешных отправок
                            await event.respond(f"✅ Отправлено {success_count}/{total_to_send}")
                        else:
                            await event.respond(f"✅ Отправлено @{username}")
                    
                    else:
                        failed_count += 1
                        await event.respond(f"❌ Ошибка отправки @{username}")
                    
                    # Задержка
                    delay = random.randint(30, 90)
                    await asyncio.sleep(delay)
                
                except Exception as e:
                    failed_count += 1
                    error_msg = str(e)
                    await event.respond(f"❌ Ошибка @{username}: {error_msg[:50]}...")
                    
                    if "FLOOD_WAIT" in error_msg:
                        try:
                            wait_time = int(error_msg.split()[-1])
                            await asyncio.sleep(wait_time)
                        except:
                            await asyncio.sleep(60)
                    else:
                        await asyncio.sleep(30)
            
            # Сохраняем историю отправки
            if sent_history:
                new_sent_df = pd.DataFrame(sent_history)
                if os.path.exists(sent_file):
                    existing_sent_df = pd.read_csv(sent_file)
                    updated_sent_df = pd.concat([existing_sent_df, new_sent_df])
                    updated_sent_df.to_csv(sent_file, index=False)
                else:
                    new_sent_df.to_csv(sent_file, index=False)
            
            # Итоговый отчет
            await event.respond(
                f"📊 **Рассылка завершена!**\n\n"
                f"✅ Успешно: {success_count}\n"
                f"❌ Ошибок: {failed_count}\n"
                f"📈 Всего обработано: {success_count + failed_count}"
            )
            
            user_states[user_id] = 'main_menu'
        
        except Exception as e:
            await event.respond(f"💥 Критическая ошибка при рассылке: {str(e)}")
            user_states[user_id] = 'main_menu'

# Запуск бота
if __name__ == '__main__':
    # Замените на токен вашего бота
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    # API данные для бота (не для пользовательских аккаунтов)
    api_id = 1234567  # Замените на ваш API ID
    api_hash = 'your_api_hash_here'  # Замените на ваш API Hash
    
    bot = MassSenderBot(BOT_TOKEN)
    
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        print("Бот остановлен")
