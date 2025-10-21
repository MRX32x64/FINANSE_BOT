import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
import os
from datetime import datetime
import pandas as pd

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Состояния для ConversationHandler
CATEGORY, AMOUNT, DESCRIPTION = range(3)

class FinanceBot:
    def __init__(self, token):
        self.token = token
        self.data_file = 'finance_data.json'
        self.load_data()
    
    def load_data(self):
        """Загружает данные из JSON файла"""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            self.data = {}
    
    def save_data(self):
        """Сохраняет данные в JSON файл"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def get_user_data(self, user_id):
        """Возвращает данные пользователя"""
        if str(user_id) not in self.data:
            self.data[str(user_id)] = {
                'transactions': [],
                'balance': 0,
                'categories': {
                    'доход': ['зарплата', 'фриланс', 'инвестиции', 'подарок'],
                    'расход': ['еда', 'транспорт', 'развлечения', 'жилье', 'здоровье']
                }
            }
        return self.data[str(user_id)]
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.message.from_user
        keyboard = [
            [KeyboardButton("📥 Добавить доход"), KeyboardButton("📤 Добавить расход")],
            [KeyboardButton("💰 Баланс"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("📋 История операций")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"Привет, {user.first_name}! 👋\n"
            "Я бот для учета финансов. Вот что я умею:\n\n"
            "📥 Добавить доход - записать поступление денег\n"
            "📤 Добавить расход - записать трату\n"
            "💰 Баланс - показать текущий баланс\n"
            "📊 Статистика - показать статистику по категориям\n"
            "📋 История - показать последние операции\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    async def add_income(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало добавления дохода"""
        user_data = self.get_user_data(update.message.from_user.id)
        categories = user_data['categories']['доход']
        
        keyboard = [[KeyboardButton(cat)] for cat in categories]
        keyboard.append([KeyboardButton("❌ Отмена")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Выберите категорию дохода:",
            reply_markup=reply_markup
        )
        return CATEGORY
    
    async def add_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало добавления расхода"""
        user_data = self.get_user_data(update.message.from_user.id)
        categories = user_data['categories']['расход']
        
        keyboard = [[KeyboardButton(cat)] for cat in categories]
        keyboard.append([KeyboardButton("❌ Отмена")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Выберите категорию расхода:",
            reply_markup=reply_markup
        )
        return CATEGORY
    
    async def category_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора категории"""
        category = update.message.text
        context.user_data['transaction'] = {'category': category}
        
        # Определяем тип операции по выбранной категории
        user_data = self.get_user_data(update.message.from_user.id)
        if category in user_data['categories']['доход']:
            context.user_data['transaction_type'] = 'income'
            prompt = "Введите сумму дохода:"
        else:
            context.user_data['transaction_type'] = 'expense'
            prompt = "Введите сумму расхода:"
        
        await update.message.reply_text(
            prompt,
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ Отмена")]], resize_keyboard=True)
        )
        return AMOUNT
    
    async def amount_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода суммы"""
        try:
            amount = float(update.message.text)
            if amount <= 0:
                await update.message.reply_text("Сумма должна быть больше 0!")
                return AMOUNT
            
            context.user_data['transaction']['amount'] = amount
            
            await update.message.reply_text(
                "Введите описание (или нажмите /skip чтобы пропустить):",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ Отмена")]], resize_keyboard=True)
            )
            return DESCRIPTION
            
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите числовое значение:")
            return AMOUNT
    
    async def description_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода описания"""
        description = update.message.text
        context.user_data['transaction']['description'] = description
        
        # Сохраняем транзакцию
        await self.save_transaction(update, context)
        return ConversationHandler.END
    
    async def skip_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Пропуск описания"""
        context.user_data['transaction']['description'] = ""
        await self.save_transaction(update, context)
        return ConversationHandler.END
    
    async def save_transaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранение транзакции"""
        user_id = update.message.from_user.id
        transaction_data = context.user_data['transaction']
        transaction_type = context.user_data['transaction_type']
        
        user_data = self.get_user_data(user_id)
        
        transaction = {
            'type': transaction_type,
            'category': transaction_data['category'],
            'amount': transaction_data['amount'],
            'description': transaction_data.get('description', ''),
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        user_data['transactions'].append(transaction)
        
        # Обновляем баланс
        if transaction_type == 'income':
            user_data['balance'] += transaction_data['amount']
        else:
            user_data['balance'] -= transaction_data['amount']
        
        self.save_data()
        
        # Показываем клавиатуру с основными командами
        keyboard = [
            [KeyboardButton("📥 Добавить доход"), KeyboardButton("📤 Добавить расход")],
            [KeyboardButton("💰 Баланс"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("📋 История операций")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        operation_type = "доход" if transaction_type == 'income' else "расход"
        await update.message.reply_text(
            f"✅ {operation_type.capitalize()} успешно добавлен!\n"
            f"Категория: {transaction_data['category']}\n"
            f"Сумма: {transaction_data['amount']} руб.\n"
            f"Описание: {transaction_data.get('description', 'нет')}",
            reply_markup=reply_markup
        )
    
    async def show_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает текущий баланс"""
        user_data = self.get_user_data(update.message.from_user.id)
        
        # Расчет доходов и расходов за все время
        total_income = sum(t['amount'] for t in user_data['transactions'] if t['type'] == 'income')
        total_expense = sum(t['amount'] for t in user_data['transactions'] if t['type'] == 'expense')
        
        await update.message.reply_text(
            f"💰 ВАШ БАЛАНС\n\n"
            f"Текущий баланс: {user_data['balance']:.2f} руб.\n"
            f"Всего доходов: {total_income:.2f} руб.\n"
            f"Всего расходов: {total_expense:.2f} руб.\n"
            f"Количество операций: {len(user_data['transactions'])}"
        )
    
    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статистику по категориям"""
        user_data = self.get_user_data(update.message.from_user.id)
        
        if not user_data['transactions']:
            await update.message.reply_text("📊 У вас пока нет операций для статистики")
            return
        
        # Статистика по категориям расходов
        expense_by_category = {}
        for transaction in user_data['transactions']:
            if transaction['type'] == 'expense':
                category = transaction['category']
                expense_by_category[category] = expense_by_category.get(category, 0) + transaction['amount']
        
        if expense_by_category:
            stats_text = "📊 СТАТИСТИКА РАСХОДОВ:\n\n"
            for category, amount in sorted(expense_by_category.items(), key=lambda x: x[1], reverse=True):
                stats_text += f"• {category}: {amount:.2f} руб.\n"
        else:
            stats_text = "Расходы пока не добавлены"
        
        await update.message.reply_text(stats_text)
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает историю операций"""
        user_data = self.get_user_data(update.message.from_user.id)
        
        if not user_data['transactions']:
            await update.message.reply_text("📋 У вас пока нет операций")
            return
        
        # Последние 10 операций
        recent_transactions = user_data['transactions'][-10:]
        history_text = "📋 ПОСЛЕДНИЕ ОПЕРАЦИИ:\n\n"
        
        for i, transaction in enumerate(reversed(recent_transactions), 1):
            emoji = "📥" if transaction['type'] == 'income' else "📤"
            operation_type = "доход" if transaction['type'] == 'income' else "расход"
            history_text += f"{emoji} {operation_type.upper()}\n"
            history_text += f"   Категория: {transaction['category']}\n"
            history_text += f"   Сумма: {transaction['amount']} руб.\n"
            history_text += f"   Дата: {transaction['date']}\n"
            if transaction['description']:
                history_text += f"   Описание: {transaction['description']}\n"
            history_text += "\n"
        
        await update.message.reply_text(history_text)
    
    async def export_to_excel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Экспортирует данные в Excel"""
        user_data = self.get_user_data(update.message.from_user.id)
        
        if not user_data['transactions']:
            await update.message.reply_text("Нет данных для экспорта")
            return
        
        df = pd.DataFrame(user_data['transactions'])
        filename = f"finance_export_{update.message.from_user.id}.xlsx"
        df.to_excel(filename, index=False)
        
        await update.message.reply_document(
            document=open(filename, 'rb'),
            filename=filename,
            caption="Ваши финансовые данные в Excel"
        )
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена операции"""
        await update.message.reply_text(
            "Операция отменена",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("📥 Добавить доход"), KeyboardButton("📤 Добавить расход")],
                [KeyboardButton("💰 Баланс"), KeyboardButton("📊 Статистика")],
                [KeyboardButton("📋 История операций")]
            ], resize_keyboard=True)
        )
        return ConversationHandler.END

def main():
    # Замените 'YOUR_BOT_TOKEN' на реальный токен бота
    TOKEN = "7893966136:AAFEQk7dGE9cKGS5mWrSWeEBZKajEFYHofQ"
    
    bot = FinanceBot(TOKEN)
    application = Application.builder().token(TOKEN).build()
    
    # ConversationHandler для добавления операций
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^(📥 Добавить доход)$"), bot.add_income),
            MessageHandler(filters.Regex("^(📤 Добавить расход)$"), bot.add_expense)
        ],
        states={
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.category_handler)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.amount_handler)],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.description_handler),
                CommandHandler("skip", bot.skip_description)
            ]
        },
        fallbacks=[CommandHandler("cancel", bot.cancel), MessageHandler(filters.Regex("^(❌ Отмена)$"), bot.cancel)]
    )
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Regex("^(💰 Баланс)$"), bot.show_balance))
    application.add_handler(MessageHandler(filters.Regex("^(📊 Статистика)$"), bot.show_statistics))
    application.add_handler(MessageHandler(filters.Regex("^(📋 История операций)$"), bot.show_history))
    application.add_handler(CommandHandler("export", bot.export_to_excel))
    
    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()