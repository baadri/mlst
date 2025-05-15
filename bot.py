# bot.py - основной файл бота
import logging
import os
import asyncio
from flight_searcher import search_flights
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv



# Загрузка переменных окружения
load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Определение состояний FSM
class FlightSearch(StatesGroup):
    waiting_for_from = State()  # Ожидание ввода города отправления
    waiting_for_to = State()    # Ожидание ввода города прибытия
    waiting_for_depart_date = State()  # Ожидание ввода даты вылета туда
    asking_return_flight = State()  # Спрашиваем, нужен ли обратный рейс
    waiting_for_return_date = State()  # Ожидание ввода даты возвращения
    waiting_for_class = State() # Ожидание выбора класса
    waiting_for_flight_type = State() # Ожидание выбора типа рейса (прямой/с пересадками)

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот для поиска авиабилетов Аэрофлота. Используй /search для начала поиска.")

# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "Я помогу найти авиабилеты Аэрофлота. Вот мои команды:\n"
        "/start - начать работу с ботом\n"
        "/search - начать поиск билетов\n"
        "/help - показать эту справку"
    )
    await message.answer(help_text)

# Обработчик команды /search
@dp.message(Command("search"))
async def cmd_search(message: types.Message, state: FSMContext):
    await state.set_state(FlightSearch.waiting_for_from)
    await message.answer("Укажите город отправления (например, Москва или MOW):")

# Обработчик ввода города отправления
@dp.message(FlightSearch.waiting_for_from)
async def process_from(message: types.Message, state: FSMContext):
    await state.update_data(from_city=message.text)
    await state.set_state(FlightSearch.waiting_for_to)
    await message.answer(f"Город отправления: {message.text}\nТеперь укажите город прибытия:")

# Обработчик ввода города прибытия
@dp.message(FlightSearch.waiting_for_to)
async def process_to(message: types.Message, state: FSMContext):
    await state.update_data(to_city=message.text)
    await state.set_state(FlightSearch.waiting_for_depart_date)
    await message.answer(f"Город прибытия: {message.text}\nУкажите дату вылета туда в формате ДД.ММ.ГГГГ:")

# Обработчик ввода даты вылета
@dp.message(FlightSearch.waiting_for_depart_date)
async def process_depart_date(message: types.Message, state: FSMContext):
    await state.update_data(depart_date=message.text)
    
    # Создаем клавиатуру для выбора, нужен ли обратный рейс
    markup = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="Да")], 
        [types.KeyboardButton(text="Нет")]
    ], resize_keyboard=True)
    
    await state.set_state(FlightSearch.asking_return_flight)
    await message.answer(f"Дата вылета: {message.text}\nНужен ли обратный рейс?", reply_markup=markup)

# Обработчик ответа на вопрос о необходимости обратного рейса
@dp.message(FlightSearch.asking_return_flight)
async def process_return_flight(message: types.Message, state: FSMContext):
    user_response = message.text.lower()
    
    if user_response == "да":
        await state.set_state(FlightSearch.waiting_for_return_date)
        await message.answer("Укажите дату обратного рейса в формате ДД.ММ.ГГГГ:")
    else:
        # Если обратный рейс не нужен, сразу переходим к выбору класса
        await state.update_data(return_date=None)
        
        # Создаем клавиатуру для выбора класса
        markup = types.ReplyKeyboardMarkup(keyboard=[
            [types.KeyboardButton(text="Эконом")], 
            [types.KeyboardButton(text="Комфорт")], 
            [types.KeyboardButton(text="Бизнес")]
        ], resize_keyboard=True)
        
        await state.set_state(FlightSearch.waiting_for_class)
        await message.answer("Выберите класс обслуживания:", reply_markup=markup)

# Обработчик ввода даты возвращения
@dp.message(FlightSearch.waiting_for_return_date)
async def process_return_date(message: types.Message, state: FSMContext):
    await state.update_data(return_date=message.text)
    
    # Создаем клавиатуру для выбора класса
    markup = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="Эконом")], 
        [types.KeyboardButton(text="Комфорт")], 
        [types.KeyboardButton(text="Бизнес")]
    ], resize_keyboard=True)
    
    await state.set_state(FlightSearch.waiting_for_class)
    await message.answer(f"Дата возвращения: {message.text}\nВыберите класс обслуживания:", reply_markup=markup)

# Обработчик выбора класса
@dp.message(FlightSearch.waiting_for_class)
async def process_class(message: types.Message, state: FSMContext):
    await state.update_data(class_type=message.text.lower())
    
        # Создаем клавиатуру для выбора типа рейса
    markup = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="Только прямые рейсы")],
        [types.KeyboardButton(text="Все рейсы")],
        [types.KeyboardButton(text="Только рейсы с пересадками")]
    ], resize_keyboard=True)
    
    await state.set_state(FlightSearch.waiting_for_flight_type)
    await message.answer("Какие рейсы вас интересуют?", reply_markup=markup)
    
    # Добавляем обработчик выбора типа рейса
@dp.message(FlightSearch.waiting_for_flight_type)
async def process_flight_type(message: types.Message, state: FSMContext):
    flight_type = message.text
    
        # Перевод выбора пользователя в значение для фильтра
    flight_filter = "all"  # По умолчанию - все рейсы
    if flight_type == "Только прямые рейсы":
        flight_filter = "direct"
    elif flight_type == "Только рейсы с пересадками":
        flight_filter = "connections"
    
    await state.update_data(flight_filter=flight_filter)
    
    # Получаем все данные из состояния
    user_data = await state.get_data()
    await state.clear()
    
    # Удаляем клавиатуру
    markup = types.ReplyKeyboardRemove()
      
    search_params = (
        f"🔍 Параметры поиска:\n"
        f"✈️ Откуда: {user_data['from_city']}\n"
        f"🛬 Куда: {user_data['to_city']}\n"
        f"📅 Дата вылета: {user_data['depart_date']}\n"
    )
    
    if user_data.get('return_date'):
        search_params += f"🔄 Дата возвращения: {user_data['return_date']}\n"
    else:
        search_params += "🔄 Без обратного рейса\n"
        
    search_params += f"🛋 Класс: {user_data.get('class_type', '—')}\n"
    
    # Добавляем информацию о типе рейса
    filter_text = "Все типы рейсов"
    if user_data.get('flight_filter') == "direct":
        filter_text = "Только прямые рейсы"
    elif user_data.get('flight_filter') == "connections":
        filter_text = "Только рейсы с пересадками"
    
    search_params += f"🛫 Тип рейса: {filter_text}"
    
    search_message = await message.answer(search_params, reply_markup=markup)
    status_message = await message.answer("🕒 Начинаю поиск билетов...")
    
    # Создаем список для хранения ссылки на сообщение статуса
    status_info = [status_message]
    
    # Функция обратного вызова для отправки статусных сообщений
    async def update_status(text):
        try:
            # Обновляем существующее сообщение статуса
            await status_info[0].edit_text(text)
        except Exception:
            # Если не удаётся обновить, отправляем новое
            status_info[0] = await message.answer(text)
    
    # Запускаем поиск билетов
    search_result = await search_flights(
        from_city=user_data['from_city'],
        to_city=user_data['to_city'],
        depart_date=user_data['depart_date'],
        return_date=user_data.get('return_date'),
        class_type=user_data.get('class_type', 'эконом'),
        flight_filter=user_data.get('flight_filter', 'all'),  # Добавляем параметр фильтрации
        status_callback=update_status
    )
    
    # Проверяем, есть ли ошибка в результате
    if "error" in search_result:
        await message.answer(f"❌ Ошибка при поиске: {search_result['error']}")
        return
    
    # Обрабатываем результаты поиска
    there_flights = search_result.get("there", [])
    back_flights = search_result.get("back", [])
    
    if not there_flights and not back_flights:
        await message.answer("❌ К сожалению, ничего не найдено. Попробуйте изменить параметры поиска.")
        return
            
    # Отправляем краткую информацию о найденных рейсах
    if there_flights:
        await message.answer(f"✅ Найдено {len(there_flights)} рейсов туда")
        
        # Отправляем информацию о каждом рейсе туда
        for flight in there_flights:
            flight_info = format_flight_info(flight, "туда")
            await message.answer(flight_info, parse_mode="HTML")
    
    if back_flights:
        await message.answer(f"✅ Найдено {len(back_flights)} рейсов обратно")
        
        # Отправляем информацию о каждом рейсе обратно
        for flight in back_flights:
            flight_info = format_flight_info(flight, "обратно")
            await message.answer(flight_info, parse_mode="HTML")
    
    # Отправляем сообщение, что поиск завершен
    await message.answer("✅ Поиск завершен! Используйте /search для нового поиска.")

def format_flight_info(flight, direction):
    """
    Форматирует информацию о рейсе для отправки в Telegram
    
    Args:
        flight: Данные о рейсе
        direction: Направление (туда/обратно)
        
    Returns:
        str: Отформатированная информация о рейсе
    """
    if flight is None:
        return f"<b>Рейс {direction}</b>\nНет информации о рейсе"
    
    # Проверка на наличие ошибки
    if "error" in flight:
        return f"<b>Рейс {direction} #{flight.get('id', '')}</b>\nОшибка: {flight.get('error', 'Неизвестная ошибка')}"
    
    segments = flight.get("segments", [])
    if not segments:
        return f"<b>Рейс {direction} #{flight.get('id', '')}</b>\nНет информации о сегментах"
    
    # Информация о количестве мест
    seats_info = f"Доступно мест: {flight.get('seats_available', '—')}"
    
    # Информация о первом сегменте (откуда и куда, время)
    first_segment = segments[0]
    last_segment = segments[-1]
    
    route_info = (
        f"<b>Рейс {direction} #{flight.get('id', '')}</b>\n"
        f"<b>{first_segment.get('depart_city', '—')} ({first_segment.get('iata_from', '—')}) → "
        f"{last_segment.get('arrive_city', '—')} ({last_segment.get('iata_to', '—')})</b>\n"
        f"Вылет: {first_segment.get('dep_time', '—')}, Прилет: {last_segment.get('arr_time', '—')}\n"
        f"{seats_info}"
    )
    
    # Добавляем информацию о стоимости
    miles_cost = flight.get('miles_cost', '—')
    rubles_cost = flight.get('rubles_cost', '—')
    
    if miles_cost != '—' and rubles_cost != '—':
        cost_info = f"\n💰 <b>Стоимость по тарифу Стандарт:</b> {miles_cost} миль + {rubles_cost} руб."
    else:
        cost_info = "\n💰 <b>Стоимость:</b> информация недоступна"
    
    route_info += cost_info
    
    # Информация о пересадках
    if flight.get("has_transfer"):
        route_info += f"\n<b>Пересадка: {flight.get('transfer_time', '—')}</b>"
    else:
        route_info += "\n<b>Прямой рейс</b>"
    
    # Добавляем информацию о сегментах, если их больше одного
    if len(segments) > 1:
        route_info += "\n\n<u>Сегменты маршрута:</u>"
        for i, segment in enumerate(segments, 1):
            route_info += (
                f"\n{i}. {segment.get('depart_city', '—')} ({segment.get('iata_from', '—')}) → "
                f"{segment.get('arrive_city', '—')} ({segment.get('iata_to', '—')})"
                f"\n   {segment.get('airline', '—')}, {segment.get('flight_number', '—')}, {segment.get('plane_model', '—')}"
                f"\n   Вылет: {segment.get('dep_time', '—')}, Прилет: {segment.get('arr_time', '—')}"
            )
    else:
        # Если только один сегмент, добавляем информацию о рейсе
        segment = segments[0]
        route_info += (
            f"\n<b>{segment.get('airline', '—')}</b>, {segment.get('flight_number', '—')}, {segment.get('plane_model', '—')}"
        )
    
    return route_info

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
