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
    waiting_for_adults = State() # Ожидание ввода количества взрослых
    waiting_for_children = State() # Ожидание ввода количества детей
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

# Обновляем обработчик ввода даты отправления или выбора обратного рейса
@dp.message(FlightSearch.asking_return_flight)
async def process_return_flight(message: types.Message, state: FSMContext):
    user_response = message.text.lower()
    
    if user_response == "да":
        await state.set_state(FlightSearch.waiting_for_return_date)
        await message.answer("Укажите дату обратного рейса в формате ДД.ММ.ГГГГ:")
    else:
        # Если обратный рейс не нужен, записываем это в состояние
        await state.update_data(return_date=None)
        
        # Переходим к выбору количества взрослых пассажиров
        # Создаем клавиатуру с кнопками от 1 до 6
        markup = types.ReplyKeyboardMarkup(keyboard=[
            [types.KeyboardButton(text="1"), types.KeyboardButton(text="2")],
            [types.KeyboardButton(text="3"), types.KeyboardButton(text="4")],
            [types.KeyboardButton(text="5"), types.KeyboardButton(text="6")]
        ], resize_keyboard=True)
        
        await state.set_state(FlightSearch.waiting_for_adults)
        await message.answer("Укажите количество взрослых пассажиров (от 1 до 6):", reply_markup=markup)

# Обновляем обработчик ввода даты возвращения
@dp.message(FlightSearch.waiting_for_return_date)
async def process_return_date(message: types.Message, state: FSMContext):
    await state.update_data(return_date=message.text)
    
    # Создаем клавиатуру с кнопками от 1 до 6
    markup = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="1"), types.KeyboardButton(text="2")],
        [types.KeyboardButton(text="3"), types.KeyboardButton(text="4")],
        [types.KeyboardButton(text="5"), types.KeyboardButton(text="6")]
    ], resize_keyboard=True)
    
    await state.set_state(FlightSearch.waiting_for_adults)
    await message.answer(f"Дата возвращения: {message.text}\nУкажите количество взрослых пассажиров (от 1 до 6):", reply_markup=markup)
    
# Добавляем обработчик выбора количества взрослых
@dp.message(FlightSearch.waiting_for_adults)
async def process_adults(message: types.Message, state: FSMContext):
    # Проверяем, что введено число от 1 до 6
    try:
        adults_count = int(message.text)
        if 1 <= adults_count <= 6:
            await state.update_data(adults_count=adults_count)
            
            # Создаем клавиатуру с кнопками от 0 до 4
            markup = types.ReplyKeyboardMarkup(keyboard=[
                [types.KeyboardButton(text="0"), types.KeyboardButton(text="1")],
                [types.KeyboardButton(text="2"), types.KeyboardButton(text="3")],
                [types.KeyboardButton(text="4")]
            ], resize_keyboard=True)
            
            await state.set_state(FlightSearch.waiting_for_children)
            await message.answer(f"Количество взрослых: {adults_count}\nУкажите количество детей (от 0 до 4):", reply_markup=markup)
        else:
            await message.answer("Пожалуйста, введите число от 1 до 6.")
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число от 1 до 6.")
        
# Добавляем обработчик выбора количества детей
@dp.message(FlightSearch.waiting_for_children)
async def process_children(message: types.Message, state: FSMContext):
    # Проверяем, что введено число от 0 до 4
    try:
        children_count = int(message.text)
        if 0 <= children_count <= 4:
            await state.update_data(children_count=children_count)
            
            # Создаем клавиатуру для выбора класса
            markup = types.ReplyKeyboardMarkup(keyboard=[
                [types.KeyboardButton(text="Эконом")], 
                [types.KeyboardButton(text="Комфорт")], 
                [types.KeyboardButton(text="Бизнес")]
            ], resize_keyboard=True)
            
            await state.set_state(FlightSearch.waiting_for_class)
            await message.answer(f"Количество детей: {children_count}\nВыберите класс обслуживания:", reply_markup=markup)
        else:
            await message.answer("Пожалуйста, введите число от 0 до 4.")
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число от 0 до 4.")

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

# Обновляем обработчик выбора типа рейса
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
    
    # Запускаем поиск с собранными данными
    await process_search_with_data(message, state, user_data)

# Функция для запуска поиска с заданными параметрами
async def process_search_with_data(message, state, user_data):
    # Удаляем клавиатуру
    markup = types.ReplyKeyboardRemove()
    
    # Формируем сообщение с параметрами поиска
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
    
    # Добавляем информацию о пассажирах
    search_params += f"👨‍👩‍👧‍👦 Пассажиры: {user_data.get('adults_count', 1)} взр."
    if user_data.get('children_count', 0) > 0:
        search_params += f" + {user_data.get('children_count')} дет."
    search_params += "\n"
        
    search_params += f"🛋 Класс: {user_data.get('class_type', '—')}\n"
    
    # Добавляем информацию о типе рейса
    filter_text = "Все типы рейсов"
    if user_data.get('flight_filter') == "direct":
        filter_text = "Только прямые рейсы"
    elif user_data.get('flight_filter') == "connections":
        filter_text = "Только рейсы с пересадками"
    
    search_params += f"🛫 Тип рейса: {filter_text}"
    
    search_message = await message.answer(search_params, reply_markup=markup)
    status_message = await message.answer("🕒 Начинаю поиск билетов с новыми параметрами...")
    
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
    
    # Запускаем поиск билетов с добавленными параметрами
    search_result = await search_flights(
        from_city=user_data['from_city'],
        to_city=user_data['to_city'],
        depart_date=user_data['depart_date'],
        return_date=user_data.get('return_date'),
        adults_count=user_data.get('adults_count', 1),
        children_count=user_data.get('children_count', 0),
        class_type=user_data.get('class_type', 'эконом'),
        flight_filter=user_data.get('flight_filter', 'all'),
        status_callback=update_status
    )
    
    # Используем существующую логику для обработки результатов
    await process_search_results(message, state, search_result)

# Выносим обработку результатов поиска в отдельную функцию для переиспользования
async def process_search_results(message, state, search_result):
    # Проверяем, есть ли ошибка в результате
    if "error" in search_result:
        # Обработка разных типов ошибок
        error_type = search_result.get("error")
        
        if error_type in ["no_flights_available", "no_direct_flights", "no_connection_flights"]:
            error_message = f"❗️ {search_result.get('message', 'На выбранные даты рейсы не найдены.')}."
            
            # Добавляем рекомендации
            if "suggestions" in search_result:
                error_message += "\n\n<b>Рекомендации:</b>"
                for suggestion in search_result["suggestions"]:
                    error_message += f"\n• {suggestion}"
                    
            # Добавляем кнопки для нового поиска и изменения типа рейса
            inline_buttons = []
            
            # Кнопка для нового поиска
            inline_buttons.append([types.InlineKeyboardButton(text="🔄 Новый поиск", callback_data="new_search")])
            
            # Добавляем кнопки для переключения типа рейса, если это связано с отсутствием определенного типа рейсов
            if error_type == "no_direct_flights":
                inline_buttons.append([types.InlineKeyboardButton(text="👁 Показать рейсы с пересадками", callback_data="show_connections")])
            elif error_type == "no_connection_flights":
                inline_buttons.append([types.InlineKeyboardButton(text="👁 Показать прямые рейсы", callback_data="show_direct")])
            
            markup = types.InlineKeyboardMarkup(inline_keyboard=inline_buttons)
            
            await message.answer(error_message, reply_markup=markup, parse_mode="HTML")
            return
        else:
            # Стандартная обработка других ошибок
            await message.answer(f"❌ Ошибка при поиске: {search_result['error']}")
            return
    
    # Обрабатываем результаты поиска
    there_flights = search_result.get("there", [])
    back_flights = search_result.get("back", [])
    
    if not there_flights and not back_flights:
        await message.answer("❌ К сожалению, ничего не найдено. Попробуйте изменить параметры поиска.")
        
        # Добавляем кнопку для нового поиска
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔄 Новый поиск", callback_data="new_search")]
        ])
        
        await message.answer("Хотите начать новый поиск?", reply_markup=markup)
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
    seats_info = f"Доступно билетов за мили: {flight.get('seats_available', '—')}"
    
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

# Обработчик для кнопки нового поиска
@dp.callback_query(lambda c: c.data == "new_search")
async def process_new_search(callback_query: types.CallbackQuery, state: FSMContext):
    # Сначала отправляем ответ на callback
    await callback_query.answer()
    
    # Начинаем новый поиск
    await state.set_state(FlightSearch.waiting_for_from)
    await callback_query.message.answer("Начинаем новый поиск! Укажите город отправления (например, Москва или MOW):")

# Обработчик кнопки "Показать рейсы с пересадками"
@dp.callback_query(lambda c: c.data == "show_connections")
async def process_show_connections(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    # Сохраняем предыдущие данные пользователя
    user_data = await state.get_data()
    
    # Обновляем данные с новым типом рейса
    user_data["flight_filter"] = "connections"
    await state.set_data(user_data)
    
    # Запускаем поиск с новым фильтром
    await process_search_with_data(callback_query.message, state, user_data)

# Обработчик кнопки "Показать прямые рейсы"
@dp.callback_query(lambda c: c.data == "show_direct")
async def process_show_direct(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    # Сохраняем предыдущие данные пользователя
    user_data = await state.get_data()
    
    # Обновляем данные с новым типом рейса
    user_data["flight_filter"] = "direct"
    await state.set_data(user_data)
    
    # Запускаем поиск с новым фильтром
    await process_search_with_data(callback_query.message, state, user_data)
    
# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
