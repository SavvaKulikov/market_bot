import sqlite3
import telebot
from telebot import types
import requests
from datetime import datetime
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#Это токен уже поднастроенного бота
API_TOKEN = '7886505530:AAF5BNbWsrkzomOGpZA24y_7Uw5DW105oBQ'
bot = telebot.TeleBot(API_TOKEN)

#Здесь должен начинаться db.py
conn = sqlite3.connect('market_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS messages (
    ID_of_message INTEGER PRIMARY KEY,
    ID_of_actor INTEGER,
    time_sent TEXT,
    text TEXT,
    is_open INTEGER,
    time_closed TEXT,
    question_id INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS chats (
    ID_of_chat INTEGER PRIMARY KEY,
    ID_of_customer INTEGER,
    ID_of_seller INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS seller_ids (
    ID_of_seller INTEGER PRIMARY KEY,
    custom_sign TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS customers (
    ID_of_customer INTEGER PRIMARY KEY
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS picks (
    ID_of_pick INTEGER PRIMARY KEY AUTOINCREMENT,
    ID_of_customer INTEGER,
    ID_of_answer INTEGER
)
''')

conn.commit()

#Здесь должен начинаться classes.py
class Customer:
    def __init__(self, ID_of_user):
        self.ID_of_user = ID_of_user

class Seller:
    def __init__(self, ID_of_user, custom_sign):
        self.ID_of_user = ID_of_user
        self.custom_sign = custom_sign

class Question:
    def __init__(self, ID_of_message, ID_of_actor, time_sent, text, is_open, time_closed):
        self.ID_of_message = ID_of_message
        self.ID_of_actor = ID_of_actor
        self.time_sent = time_sent
        self.text = text
        self.is_open = is_open
        self.time_closed = time_closed

class Answer:
    def __init__(self, ID_of_message, ID_of_actor, time_sent, text, question_id):
        self.ID_of_message = ID_of_message
        self.ID_of_actor = ID_of_actor
        self.time_sent = time_sent
        self.text = text
        self.question_id = question_id

# Здесь должен начинаться utils.py (что-то на стыке модели и работы с базой данных)
def initialize_customer(ID_of_user):
    cursor.execute('INSERT OR IGNORE INTO customers (ID_of_customer) VALUES (?)', (ID_of_user,))
    conn.commit()
    logging.info(f"User {ID_of_user} registered as a customer.")
    return Customer(ID_of_user)

def initialize_seller(ID_of_user, custom_sign):
    cursor.execute('INSERT OR IGNORE INTO seller_ids (ID_of_seller) VALUES (?)', (ID_of_user,))
    conn.commit()
    logging.info(f"User {ID_of_user} registered as a seller with custom sign: {custom_sign}.")
    return Seller(ID_of_user, custom_sign)

def initialize_question(customer, text):
    time_sent = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT INTO messages (ID_of_actor, time_sent, text, is_open) VALUES (?, ?, ?, ?)',
                   (customer.ID_of_user, time_sent, text, 1))
    conn.commit()
    ID_of_message = cursor.lastrowid
    question = Question(ID_of_message, customer.ID_of_user, time_sent, text, 1, None)

    # Отправка запроса продавцам
    cursor.execute('SELECT ID_of_seller FROM seller_ids')
    seller_ids = cursor.fetchall()
    for seller_id in seller_ids:
        bot.send_message(seller_id[0], f"Новый запрос от покупателя: [{ID_of_message}] {text}")

    logging.info(f"Question {ID_of_message} created by customer {customer.ID_of_user}: {text}")
    return question

def initialize_answer(question, seller, text):
    time_sent = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print("Мы здесь!")
    print(seller.ID_of_user, time_sent, text, 2, question.ID_of_message)
    cursor.execute('INSERT INTO messages (ID_of_actor, time_sent, text, is_open, question_id) VALUES (?, ?, ?, ?, ?)',
                   (seller.ID_of_user, time_sent, text, 2, question.ID_of_message,))
    conn.commit()
    ID_of_message = cursor.lastrowid
    answer = Answer(ID_of_message, seller.ID_of_user, time_sent, text, question.ID_of_message)

    # Отправка сообщения создателю вопроса
    bot.send_message(question.ID_of_actor, f"Новый ответ от продавца: {text} (ID ответа: {ID_of_message})")

    logging.info(f"Answer {ID_of_message} created by seller {seller.ID_of_user} for question {question.ID_of_message}: {text}")
    return answer

def load_customer(id):
    cursor.execute('SELECT ID_of_customer FROM customers WHERE ID_of_customer = ?', (id,))
    result = cursor.fetchone()[0]
    print(result)
    if result is None: return Customer(None)
    return Customer(result[0])
def load_seller(id):
    cursor.execute('SELECT ID_of_seller FROM seller_ids WHERE ID_of_seller = ?', (id,))
    ID_of_seller = cursor.fetchone()
    cursor.execute('SELECT custom_sign FROM seller_ids WHERE ID_of_seller = ?', (id,))
    print(ID_of_seller)
    custom_sign = cursor.fetchone()
    if ID_of_seller is None: return Seller(None, None)
    return Seller(ID_of_seller, custom_sign)
def load_question(id):
    cursor.execute('SELECT ID_of_message, ID_of_actor, time_sent, text, is_open, time_closed FROM messages WHERE ID_of_message = ? AND (is_open = 1 OR is_open = 0)', (id,))
    result = cursor.fetchone()
    # print(result)
    if result is None: return Question(None, None, None, None, 0, None)
    question = Question(result[0], result[1], result[2], result[3], result[4], result[5])
    return question

def load_answer(id):
    cursor.execute('SELECT ID_of_message, ID_of_actor, time_sent, text, question_id FROM messages WHERE ID_of_message = ? AND is_open = 2',(id,))
    result = cursor.fetchone()
    if result is None: return Answer(None, None, None, None, None)
    answer = Answer(result[0], result[1], result[2], result[3], result[4])
    return answer

def close_question(question):
    question.is_open = 0
    question.time_closed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('UPDATE messages SET is_open = ?, time_closed = ? WHERE ID_of_message = ?',
                   (question.is_open, question.time_closed, question.ID_of_message))
    conn.commit()
    logging.info(f"Question {question.ID_of_message} closed by customer {question.ID_of_actor}.")

# Здесь должен начинаться bot.py
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(message.chat.id, "Привет! Я бот для взаимодействия между покупателями и продавцами на радиорынке. Что вы хотите сделать?", parse_mode='Markdown')
    logging.info(f"User {message.from_user.id} started the bot.")
    if load_customer(message.from_user.id).ID_of_user is None and load_seller(message.from_user.id).ID_of_user is None:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_customer = types.KeyboardButton('/customer')
        btn_seller = types.KeyboardButton('/seller')
        markup.add(btn_customer, btn_seller)
        register_text = "Зарегистрируйтесь как продавец (/seller) или покупатель (/customer)"
        bot.send_message(message.chat.id, register_text, reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def handle_help(message):
    show_help(message)
    logging.info(f"User {message.from_user.id} requested help.")

def show_help(message):
    help_text = (
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/customer - Зарегистрироваться как покупатель\n"
        "/seller - Зарегистрироваться как продавец\n"
        "/ask [текст] - Создать вопрос (только для покупателей)\n"
        "/reply [ID вопроса] [текст] - Ответить на вопрос (только для продавцов)\n"
        "/pick [ID ответа] - Выбрать ответ (только для покупателей)\n"
        "/close [ID вопроса] - Закрыть вопрос (только для покупателей)\n"
        "/requests - Показать список запросов\n"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['customer'])
def handle_customer(message):
    user_id = message.from_user.id
    markup = types.ReplyKeyboardRemove()
    if load_customer(user_id).ID_of_user is not None:
        bot.send_message(message.chat.id, "Вы уже зарегистрированы как покупатель.", parse_mode='Markdown')
        logging.info(f"User {user_id} attempted to register as a customer but is already registered.")
    else:
        if load_seller(user_id).ID_of_user is not None:
            bot.send_message(message.chat.id, "Вы уже зарегистрированы как продавец и не можете быть покупателем.", parse_mode='Markdown')
            logging.info(f"User {user_id} attempted to register as a customer but is already registered as a seller.")
        else:
            initialize_customer(user_id)
            bot.send_message(message.chat.id, "Вы зарегистрированы как покупатель.", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['seller'])
def handle_seller(message):
    user_id = message.from_user.id
    markup = types.ReplyKeyboardRemove()
    custom_sign = message.text.split(' ', 1)[1] if len(message.text.split(' ', 1)) > 1 else ''
    if load_seller(user_id).ID_of_user is not None:
        bot.send_message(message.chat.id, "Вы уже зарегистрированы как продавец.", parse_mode='Markdown')
        logging.info(f"User {user_id} attempted to register as a seller but is already registered.")
    else:
        if load_customer(user_id).ID_of_user is not None:
            bot.send_message(message.chat.id, "Вы уже зарегистрированы как покупатель и не можете быть продавцом.", parse_mode='Markdown')
            logging.info(f"User {user_id} attempted to register as a seller but is already registered as a customer.")
        else:
            initialize_seller(user_id, custom_sign)
            bot.send_message(message.chat.id, "Вы зарегистрированы как продавец.", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['ask'])
def handle_ask(message):
    try:
        user_id = message.from_user.id
        if load_customer(user_id).ID_of_user is not None:
            if len(message.text.split(' ', 1)) > 1:
                text = message.text.split(' ', 1)[1]
                customer = load_customer(user_id)
                question = initialize_question(customer, text)
                bot.send_message(user_id, f"Ваш запрос №{question.ID_of_message} отправлен продавцам. Ожидайте ответов.", parse_mode='Markdown')
            else:
                bot.send_message(message.chat.id, "Запрос должен содержать текст.", parse_mode='Markdown')
        else:
            bot.send_message(user_id, "Вы не зарегистрированы как покупатель. Используйте команду /customer для регистрации.", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.", parse_mode='Markdown')

@bot.message_handler(commands=['reply'])
def handle_reply(message):
    try:
        user_id = message.from_user.id
        parts = message.text.split(' ', 2)
        if len(parts) <= 1:
            bot.send_message(message.chat.id, "Используйте команду в формате: /reply [ID вопроса] [Текст ответа]", parse_mode='Markdown')
            return

        question_id = int(parts[1])
        text = parts[2]

        if load_seller(user_id).ID_of_user is not None:
            seller = load_seller(user_id)
            if load_question(question_id).ID_of_message is not None and load_question(question_id).is_open == 1:
                initialize_answer(load_question(question_id), seller, text)
                bot.send_message(user_id, "Ваш ответ отправлен покупателю.", parse_mode='Markdown')
            else:
                bot.send_message(user_id, "Запрос с таким ID не найден или уже закрыт.", parse_mode='Markdown')
        else:
            bot.send_message(user_id, "Вы не зарегистрированы как продавец. Используйте команду /seller для регистрации.", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.", parse_mode='Markdown')

@bot.message_handler(commands=['pick'])
def handle_pick(message):
    try:
        user_id = message.from_user.id
        parts = message.text.split(' ', 2)
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Используйте команду в формате: /pick [ID ответа]", parse_mode='Markdown')
            return

        answer_id = int(parts[1])

        if load_customer(user_id).ID_of_user is not None:
            if load_answer(answer_id).ID_of_message is not None:
                answer = load_answer(answer_id)
                cursor.execute('SELECT 1 FROM picks WHERE ID_of_customer = ? AND ID_of_answer = ?', (user_id, answer_id))
                if cursor.fetchone():
                    seller_link = f"tg://user?id={answer.ID_of_actor}"
                    bot.send_message(user_id, f"Вы уже взяли это предложение. ID продавца - [ID]({seller_link})", parse_mode='Markdown')
                else:
                    cursor.execute('INSERT INTO picks (ID_of_customer, ID_of_answer) VALUES (?, ?)', (user_id, answer_id))
                    conn.commit()
                    seller_link = f"tg://user?id={answer.ID_of_actor}"
                    bot.send_message(answer.ID_of_actor, f"Покупатель {user_id} выбрал ваш ответ на запрос [{answer.ID_of_actor}]", parse_mode='Markdown')
                    bot.send_message(user_id, f"Вы выбрали ответ от продавца {seller_link} на запрос [{answer.question_id}]", parse_mode='Markdown')
            else:
                bot.send_message(user_id, "Ответ с таким ID не найден или запрос уже закрыт.", parse_mode='Markdown')
        else:
            bot.send_message(user_id, "Вы не зарегистрированы как покупатель. Используйте команду /customer для регистрации.", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.", parse_mode='Markdown')

@bot.message_handler(commands=['close'])
def handle_close(message):
    try:
        user_id = message.from_user.id
        parts = message.text.split(' ', 2)
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Используйте команду в формате: /close [ID запроса]", parse_mode='Markdown')
            return

        question_id = int(parts[1])

        if load_customer(user_id).ID_of_user is not None:
            if load_question(question_id).ID_of_message is not None and load_question(question_id).is_open == 1:
                close_question(Question(question_id, user_id, '', '', 1, None))
                bot.send_message(user_id, "Запрос закрыт.", parse_mode='Markdown')
            else:
                bot.send_message(user_id, "Запрос с таким ID не найден или уже закрыт.", parse_mode='Markdown')
        else:
            bot.send_message(user_id, "Вы не зарегистрированы как покупатель. Используйте команду /customer для регистрации.", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.", parse_mode='Markdown')

@bot.message_handler(commands=['requests'])
def handle_requests(message):
    try:
        user_id = message.from_user.id
        # Проверка, является ли пользователь продавцом
        if load_seller(user_id).ID_of_user is not None:
            cursor.execute('SELECT ID_of_message, ID_of_actor, time_sent, text, is_open FROM messages WHERE is_open = 1')
            questions = cursor.fetchall()
            if questions:
                questions_list = "\n".join([f"ID: {row[0]}, Открыто: {row[2]}, {row[3]}" for row in questions])
                bot.send_message(message.chat.id, f"Список открытых запросов:\n{questions_list}", parse_mode='Markdown')
            else:
                bot.send_message(message.chat.id, "Нет открытых запросов.", parse_mode='Markdown')
        else:
            cursor.execute('SELECT ID_of_message, ID_of_actor, time_sent, text, is_open FROM messages WHERE ID_of_actor = ? AND is_open = 1', (user_id,))
            questions = cursor.fetchall()
            if questions:
                questions_list = "\n".join([f"ID: {row[0]}, Открыто: {row[2]}, {row[3]}" for row in questions])
                bot.send_message(message.chat.id, f"Список ваших открытых запросов:\n{questions_list}", parse_mode='Markdown')
            else:
                bot.send_message(message.chat.id, "У вас нет открытых запросов.", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.", parse_mode='Markdown')

def start_bot():
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except requests.exceptions.ReadTimeout:
            logging.error("Read timeout occurred. Retrying...")
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            time.sleep(5)

if __name__ == '__main__':
    start_bot()