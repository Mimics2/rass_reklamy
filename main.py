import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import List
import pytz
from telethon import TelegramClient, events

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Данные вашего аккаунта
API_ID = 34926321
API_HASH = '3ce3de5ab33d2defac471e34d47662e2'
PHONE_NUMBER = '+79123456789'  # Ваш номер телефона с кодом страны

class BaroHologSender:
    def __init__(self, api_id: int, api_hash: str):
        self.client = TelegramClient('baroholog_session', api_id, api_hash)
        self.chats_list = []  # Будем хранить объекты чатов
        self.is_active = False
        self.scheduled_tasks = []
        
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        self.client.on(events.NewMessage(pattern='/start'))(self.start_command)
        self.client.on(events.NewMessage(pattern='/add_chats'))(self.add_chats_command)
        self.client.on(events.NewMessage(pattern='/start_bot'))(self.start_bot_command)
        self.client.on(events.NewMessage(pattern='/status'))(self.status_command)
        self.client.on(events.NewMessage(pattern='/stop_bot'))(self.stop_bot_command)
    
    async def start_command(self, event):
        """Обработчик команды /start"""
        if not await self.is_owner(event):
            return
            
        instructions = """
🤖 **Рассылка рекламных сообщений BaroHolog**

**Доступные команды:**

📝 `/add_chats` - Добавить чаты для рассылки (ответьте на сообщение из чата)
▶️ `/start_bot` - Запуск автоматической рассылки
🛑 `/stop_bot` - Остановить рассылку
📊 `/status` - Проверить статус
🆘 `/start` - Показать инструкцию

**Расписание рассылки:**
⏰ 09:00 по Москве - первая публикация
⏰ 17:00 по Москве - вторая публикация

**Важно:** Строго 2 публикации в день в указанное время.
        """
        await event.reply(instructions)
    
    async def add_chats_command(self, event):
        """Обработчик команды /add_chats"""
        if not await self.is_owner(event):
            return
        
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            chat = await event.get_chat()
            
            chat_info = {
                'id': chat.id,
                'title': getattr(chat, 'title', 'Private Chat'),
                'username': getattr(chat, 'username', None),
                'entity': chat
            }
            
            if not any(c['id'] == chat_info['id'] for c in self.chats_list):
                self.chats_list.append(chat_info)
                await event.reply(
                    f"✅ Чат добавлен: {chat_info['title']}\n"
                    f"📊 Всего чатов: {len(self.chats_list)}"
                )
            else:
                await event.reply("❌ Этот чат уже добавлен")
        else:
            await event.reply(
                "📝 **Добавление чатов**\n\n"
                "Чтобы добавить чат:\n"
                "1. Перейдите в нужный чат/группу\n"
                "2. Ответьте на любое сообщение командой `/add_chats`\n\n"
                "Или перешлите сообщение из чата с командой `/add_chats`"
            )
    
    async def start_bot_command(self, event):
        """Обработчик команды /start_bot"""
        if not await self.is_owner(event):
            return
            
        if not self.chats_list:
            await event.reply("❌ Сначала добавьте чаты с помощью `/add_chats`")
            return
            
        if self.is_active:
            await event.reply("❌ Рассылка уже активна")
            return
        
        self.is_active = True
        await self.setup_schedule()
        
        chat_names = "\n".join([f"• {chat['title']}" for chat in self.chats_list])
        
        await event.reply(
            f"✅ **Рассылка запущена!**\n\n"
            f"📊 Чатов для рассылки: {len(self.chats_list)}\n"
            f"⏰ Расписание: 09:00 и 17:00 по Москве\n"
            f"📢 Публикаций в день: 2\n\n"
            f"Чаты:\n{chat_names}"
        )
    
    async def stop_bot_command(self, event):
        """Остановка рассылки"""
        if not await self.is_owner(event):
            return
            
        if not self.is_active:
            await event.reply("❌ Рассылка и так не активна")
            return
            
        await self.stop_bot()
        await event.reply("🛑 Рассылка остановлена")
    
    async def status_command(self, event):
        """Обработчик команды /status"""
        if not await self.is_owner(event):
            return
            
        status_text = "🟢 АКТИВНА" if self.is_active else "🔴 НЕ АКТИВНА"
        
        status_message = (
            f"🤖 **Статус рассылки BaroHolog**\n\n"
            f"📊 Статус: {status_text}\n"
            f"👥 Чатов в списке: {len(self.chats_list)}\n"
            f"📅 Время проверки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        
        if self.chats_list:
            status_message += "\n📋 Список чатов:\n" + "\n".join([f"• {chat['title']}" for chat in self.chats_list[:5]])
            if len(self.chats_list) > 5:
                status_message += f"\n... и еще {len(self.chats_list) - 5} чатов"
        else:
            status_message += "\n📝 Чаты не добавлены"
            
        await event.reply(status_message)
    
    async def is_owner(self, event):
        """Проверка, что команда от владельца аккаунта"""
        sender = await event.get_sender()
        me = await self.client.get_me()
        return sender.id == me.id
    
    async def setup_schedule(self):
        """Настройка расписания рассылки"""
        # Очищаем предыдущие задачи
        for task in self.scheduled_tasks:
            task.cancel()
        self.scheduled_tasks.clear()
        
        # Создаем задачи для двух времен
        times = [time(9, 0), time(17, 0)]  # 09:00 и 17:00 по Москве
        
        for send_time in times:
            task = asyncio.create_task(self.schedule_sender(send_time))
            self.scheduled_tasks.append(task)
            
        logger.info(f"Настроено расписание для {len(times)} времен")
    
    async def schedule_sender(self, send_time: time):
        """Планировщик рассылки для конкретного времени"""
        moscow_tz = pytz.timezone('Europe/Moscow')
        
        while self.is_active:
            try:
                now = datetime.now(moscow_tz)
                target_time = moscow_tz.localize(datetime.combine(now.date(), send_time))
                
                # Если время уже прошло сегодня, планируем на завтра
                if now > target_time:
                    target_time += timedelta(days=1)
                
                wait_seconds = (target_time - now).total_seconds()
                logger.info(f"Следующая рассылка в {send_time} через {wait_seconds:.0f} секунд")
                
                # Ждем до времени рассылки
                await asyncio.sleep(wait_seconds)
                
                if self.is_active:
                    await self.send_messages()
                
                # Ждем до следующего дня
                await asyncio.sleep(86400 - wait_seconds)  # Ожидание до следующего дня
                
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                await asyncio.sleep(60)
    
    async def send_messages(self):
        """Отправка сообщений во все чаты"""
        if not self.is_active or not self.chats_list:
            return
            
        logger.info(f"Начало рассылки в {len(self.chats_list)} чатов")
        
        success_count = 0
        fail_count = 0
        
        for chat_info in self.chats_list:
            try:
                message_text = """
📢 **Рекламное сообщение BaroHolog** 📢

Ваше рекламное сообщение здесь...

✨ Преимущества:
• Высокое качество
• Быстрая доставка  
• Отличная поддержка

📞 Контакты: ваш контакт
                """
                
                await self.client.send_message(
                    entity=chat_info['entity'],
                    message=message_text
                )
                success_count += 1
                logger.info(f"Сообщение отправлено в {chat_info['title']}")
                
                # Пауза между отправками
                await asyncio.sleep(3)
                
            except Exception as e:
                fail_count += 1
                logger.error(f"Ошибка отправки в {chat_info['title']}: {e}")
        
        # Отправляем отчет себе
        report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        report_message = (
            f"📊 **Отчет о рассылке**\n\n"
            f"⏰ Время: {report_time}\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Ошибок: {fail_count}\n"
            f"📊 Всего чатов: {len(self.chats_list)}"
        )
        
        try:
            me = await self.client.get_me()
            await self.client.send_message(me.id, report_message)
        except Exception as e:
            logger.error(f"Не удалось отправить отчет: {e}")
    
    async def stop_bot(self):
        """Остановка рассылки"""
        self.is_active = False
        for task in self.scheduled_tasks:
            task.cancel()
        self.scheduled_tasks.clear()
        logger.info("Рассылка остановлена")
    
    async def run(self):
        """Запуск клиента"""
        await self.client.start(phone=PHONE_NUMBER)
        self.setup_handlers()
        
        me = await self.client.get_me()
        logger.info(f"Работаем от имени: {me.first_name} (ID: {me.id})")
        
        await self.client.send_message(me.id, "✅ Рассыльщик BaroHolog запущен! Используйте /start для инструкций")
        
        await self.client.run_until_disconnected()

# Запуск
async def main():
    sender = BaroHologSender(API_ID, API_HASH)
    await sender.run()

if __name__ == "__main__":
    asyncio.run(main())
