# flight_searcher.py
import asyncio
import re
import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
# Импортируем словарь из отдельного файла
from city_codes import CITY_TO_IATA

# словарь соответствия классов обслуживания
CLASS_MAP = {
    "эконом": "economy",
    "комфорт": "comfort",
    "бизнес": "business"
}

async def create_browser():
    """
    Создает и возвращает экземпляр браузера
    
    Returns:
        tuple: (driver, wait) - экземпляр WebDriver и WebDriverWait
    """
    # Используем относительный или абсолютный путь в зависимости от ОС
    chromedriver_path = 'chromedriver.exe' if os.name == 'nt' else './chromedriver'
    service = Service(chromedriver_path)
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()
    wait = WebDriverWait(driver, 15)  # Увеличиваем время ожидания до 15 секунд
    return driver, wait

async def search_flights(
    from_city, 
    to_city, 
    depart_date, 
    return_date=None,  # Этот параметр оставляем для обратной совместимости, но не используем
    adults_count=1,
    children_count=0,
    class_type="economy", 
    flight_filter="all",
    status_callback=None,
    driver=None,
    wait=None
):
    """
    асинхронная функция для поиска авиабилетов через Selenium.
    
    Args:
        from_city (str): город отправления
        to_city (str): город прибытия
        depart_date (str): дата вылета в формате дд.мм.гггг
        return_date (str, optional): параметр для обратной совместимости
        adults_count (int, optional): количество взрослых пассажиров (от 1 до 6)
        children_count (int, optional): количество детей (от 0 до 4)
        class_type (str, optional): класс обслуживания (эконом, комфорт, бизнес)
        flight_filter (str, optional): фильтр типа рейса ('all', 'direct', 'connections')
        status_callback (callable, optional): функция для отправки статусных сообщений
        driver (WebDriver, optional): экземпляр WebDriver для повторного использования
        wait (WebDriverWait, optional): экземпляр WebDriverWait для повторного использования
        
    Returns:
        tuple: (результаты поиска, флаг нужно ли закрывать браузер)
    """
    # Флаг, указывающий, создали ли мы браузер в этой функции
    browser_created_here = False
    
    # если передан код города, используем его, иначе пытаемся определить по названию
    from_code = from_city.upper() if len(from_city) == 3 else CITY_TO_IATA.get(from_city.lower(), from_city)
    to_code = to_city.upper() if len(to_city) == 3 else CITY_TO_IATA.get(to_city.lower(), to_city)
    
    # проверка формата даты и преобразование в формат YYYYMMDD для URL
    try:
        depart_date_obj = datetime.strptime(depart_date, '%d.%m.%Y')
        formatted_depart_date = depart_date_obj.strftime('%Y%m%d')
    except ValueError:
        if status_callback:
            await status_callback("❌ неверный формат даты! используйте формат дд.мм.гггг")
        return {"error": "Invalid date format"}, browser_created_here
    
    # определяем класс обслуживания
    service_class = CLASS_MAP.get(class_type.lower(), "economy")
    
    # Проверяем и ограничиваем количество пассажиров
    adults_count = max(1, min(6, int(adults_count)))  # от 1 до 6
    children_count = max(0, min(4, int(children_count)))  # от 0 до 4
    
    # формируем URL для поиска, явно указывая количество пассажиров
    url = f'https://www.aeroflot.ru/sb/app/ru-ru#/search?adults={adults_count}&children={children_count}&childrenaward={children_count}&award=Y&cabin={service_class}&infants=0'
    
    # Всегда используем маршрут в одну сторону
    url += f'&routes={from_code}.{formatted_depart_date}.{to_code}'
    
    if status_callback:
        await status_callback(f"🔍 начинаю поиск билетов...\n👥 Пассажиры: {adults_count} взр., {children_count} дет.\nURL: {url}")
    
    # Если браузер не передан, создаем новый экземпляр
    if driver is None or wait is None:
        browser_created_here = True
        try:
            driver, wait = await create_browser()
        except Exception as e:
            if status_callback:
                await status_callback(f"❌ Не удалось запустить браузер: {str(e)}")
            return {"error": f"Browser initialization failed: {str(e)}"}, browser_created_here
    
    results = {"there": []}  # Упрощаем структуру результатов
    
    try:
        if status_callback:
            await status_callback("🌐 открываю сайт аэрофлота...")
        
        driver.get(url)
        
        # Ожидание загрузки страницы и появления кнопки "найти"
        wait = WebDriverWait(driver, 5)
        try:
            if status_callback:
                await status_callback("🔍 нажимаю кнопку поиска...")
                
            find_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@class,'button') and contains(.,'Найти')]"))
            )
            find_button.click()
        except (NoSuchElementException, TimeoutException):
            if status_callback:
                await status_callback("⚠️ кнопка 'найти' не найдена или не кликабельна")
            return {"error": "Search button not found"}, browser_created_here

        # Проверяем наличие сообщения "На выбранные даты рейсы не найдены"
        try:
            # Сначала увеличиваем время ожидания, так как страница может долго грузиться
            wait = WebDriverWait(driver, 15)
            
            # Проверяем, есть ли сообщение о том, что нет рейсов
            no_flights_message = driver.find_elements(By.XPATH, 
                "//div[contains(@class,'text') and contains(@role,'alert') and contains(text(),'На выбранные даты рейсы не найдены')]")
            
            if no_flights_message:
                if status_callback:
                    await status_callback("ℹ️ На выбранные даты рейсы не найдены. Попробуйте изменить дату, уменьшить количество пассажиров.")
                return {
                    "error": "no_flights_available",
                    "message": "На выбранные даты рейсы не найдены",
                    "suggestions": [
                        "Выберите другую дату",
                        "Уменьшите количество пассажиров",
                        f"Текущее количество пассажиров: {adults_count} взр., {children_count} дет.",
                        "Попробуйте другой класс обслуживания"
                    ]
                }, browser_created_here

            # Ожидание результатов поиска
            try:
                if status_callback:
                    await status_callback("⏳ ожидаю результаты поиска...")
                
                wait.until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'flight-search__inner')]"))
                )
                # Добавляем еще немного времени на полную загрузку
                await asyncio.sleep(3)
            except TimeoutException:
                # Проверяем еще раз, не появилось ли сообщение об отсутствии рейсов
                no_flights_message = driver.find_elements(By.XPATH, 
                    "//div[contains(@class,'text') and contains(@role,'alert') and contains(text(),'На выбранные даты рейсы не найдены')]")
                
                if no_flights_message:
                    if status_callback:
                        await status_callback("ℹ️ На выбранные даты рейсы не найдены. Попробуйте изменить дату, уменьшить количество пассажиров.")
                    return {
                        "error": "no_flights_available",
                        "message": "На выбранные даты рейсы не найдены",
                        "suggestions": [
                            "Выберите другую дату",
                            "Уменьшите количество пассажиров",
                            f"Текущее количество пассажиров: {adults_count} взр., {children_count} дет.",
                            "Попробуйте другой класс обслуживания"
                        ]
                    }, browser_created_here
                        
                if status_callback:
                    await status_callback("⚠️ Timeout: результаты поиска не загрузились за отведенное время")
                return {"error": "Search results timeout"}, browser_created_here
                
        except Exception as e:
            # Если произошла ошибка при проверке наличия сообщений, продолжаем обычный поиск
            print(f"Error checking no flights message: {e}")
        
        # Добавляем логику применения фильтра по типу рейса
        if flight_filter != "all":
            if status_callback:
                await status_callback("🔍 применяю фильтр по типу рейса...")
            
            try:
                # Ждем появления фильтров
                wait.until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'filter__title')]"))
                )
                
                # Проверяем, нужно ли раскрыть аккордеон с экспресс-фильтрами
                accordion_item = driver.find_elements(By.XPATH, "//div[@role='tab' and contains(@class,'accordion__item') and .//span[contains(text(),'Экспресс-фильтры')]]")
                if accordion_item:
                    if not "accordion__item--open" in accordion_item[0].get_attribute("class"):
                        # Если аккордеон закрыт, кликаем по нему чтобы открыть
                        accordion_button = accordion_item[0].find_element(By.XPATH, ".//button[contains(@class,'accordion__heading')]")
                        driver.execute_script("arguments[0].click();", accordion_button)
                        await asyncio.sleep(1)
                
                # Проверяем наличие фильтра "Прямой рейс"
                direct_checkbox_labels = driver.find_elements(By.XPATH, "//label[contains(text(),'Прямой рейс')]")
                if not direct_checkbox_labels and flight_filter == "direct":
                    # Если фильтр "Прямой рейс" отсутствует, но пользователь запросил только прямые рейсы
                    if status_callback:
                        await status_callback("ℹ️ На выбранные даты прямые рейсы за мили не найдены.")
                    return {
                        "error": "no_direct_flights",
                        "message": "На выбранные даты прямые рейсы за мили не найдены",
                        "suggestions": [
                            "Выберите другую дату",
                            "Выберите вариант 'Все рейсы', чтобы увидеть рейсы с пересадками",
                            f"Текущее количество пассажиров: {adults_count} взр., {children_count} дет.",
                            "Попробуйте другой класс обслуживания"
                        ]
                    }, browser_created_here
                
                if flight_filter == "direct":
                    # Находим чекбокс "Прямой рейс"
                    direct_checkbox_label = wait.until(
                        EC.presence_of_element_located((By.XPATH, "//label[contains(text(),'Прямой рейс')]"))
                    )
                    direct_checkbox_id = direct_checkbox_label.get_attribute("for")
                    direct_checkbox = driver.find_element(By.ID, direct_checkbox_id)
                    
                    # Включаем только прямые рейсы
                    if not direct_checkbox.is_selected():
                        driver.execute_script("arguments[0].click();", direct_checkbox)
                        
                    # Находим чекбокс "1" (с одной пересадкой), если он существует
                    connection_checkbox_labels = driver.find_elements(By.XPATH, "//label[text()='1']")
                    if connection_checkbox_labels:
                        connection_checkbox_label = connection_checkbox_labels[0]
                        connection_checkbox_id = connection_checkbox_label.get_attribute("for")
                        connection_checkbox = driver.find_element(By.ID, connection_checkbox_id)
                        
                        # Убеждаемся, что рейсы с пересадками выключены
                        if connection_checkbox.is_selected():
                            driver.execute_script("arguments[0].click();", connection_checkbox)
                        
                elif flight_filter == "connections":
                    # Проверяем наличие фильтра "1" (с одной пересадкой)
                    connection_checkbox_labels = driver.find_elements(By.XPATH, "//label[text()='1']")
                    if not connection_checkbox_labels:
                        if status_callback:
                            await status_callback("ℹ️ На выбранные даты рейсы с пересадками за мили не найдены.")
                        return {
                            "error": "no_connection_flights",
                            "message": "На выбранные даты рейсы с пересадками за мили не найдены",
                            "suggestions": [
                                "Выберите другую дату",
                                "Выберите вариант 'Все рейсы', чтобы увидеть прямые рейсы",
                                f"Текущее количество пассажиров: {adults_count} взр., {children_count} дет.",
                                "Попробуйте другой класс обслуживания"
                            ]
                        }, browser_created_here
                    
                    # Включаем только рейсы с пересадками
                    connection_checkbox_label = connection_checkbox_labels[0]
                    connection_checkbox_id = connection_checkbox_label.get_attribute("for")
                    connection_checkbox = driver.find_element(By.ID, connection_checkbox_id)
                    if not connection_checkbox.is_selected():
                        driver.execute_script("arguments[0].click();", connection_checkbox)
                    
                    # Убеждаемся, что прямые рейсы выключены, если такой фильтр существует
                    direct_checkbox_labels = driver.find_elements(By.XPATH, "//label[contains(text(),'Прямой рейс')]")
                    if direct_checkbox_labels:
                        direct_checkbox_label = direct_checkbox_labels[0]
                        direct_checkbox_id = direct_checkbox_label.get_attribute("for")
                        direct_checkbox = driver.find_element(By.ID, direct_checkbox_id)
                        if direct_checkbox.is_selected():
                            driver.execute_script("arguments[0].click();", direct_checkbox)
                
                # Даем время на применение фильтра
                await asyncio.sleep(2)
                
                if status_callback:
                    await status_callback("✅ фильтр по типу рейса применен")
                    
            except (NoSuchElementException, TimeoutException) as e:
                if status_callback:
                    await status_callback(f"⚠️ не удалось применить фильтр по типу рейса: {str(e)}")
        
        # Обработка результатов поиска
        try:
            if status_callback:
                await status_callback("✅ результаты поиска получены, обрабатываю данные...")
            
            # найдем заголовки направлений (туда и обратно)
            direction_frames = driver.find_elements(By.XPATH, "//div[contains(@class,'frame__heading') and contains(@class,'h-pull--left')]")
            
            # Если заголовки не найдены, проверяем страницу еще раз
            if not direction_frames:
                if status_callback:
                    await status_callback("⚠️ не найдены заголовки направлений, проверяю страницу еще раз...")
                
                # Проверяем, есть ли сообщение о том, что нет рейсов
                no_flights_message = driver.find_elements(By.XPATH, 
                    "//div[contains(@class,'text') and @role='alert' and contains(text(),'На выбранные даты')]")
                
                if no_flights_message:
                    if status_callback:
                        await status_callback(f"ℹ️ {no_flights_message[0].text}. Попробуйте изменить дату или уменьшить количество пассажиров.")
                    return {
                        "error": "no_flights_available",
                        "message": no_flights_message[0].text,
                        "suggestions": [
                            "Выберите другую дату",
                            "Уменьшите количество пассажиров",
                            f"Текущее количество пассажиров: {adults_count} взр., {children_count} дет.",
                            "Попробуйте другой класс обслуживания"
                        ]
                    }, browser_created_here
                
                # Если мы дошли сюда, то нет ни результатов, ни сообщения об отсутствии рейсов
                if status_callback:
                    await status_callback("⚠️ не найдены направления рейсов, но страница загружена")
                return {"error": "No directions found"}, browser_created_here
            
            # Обработка найденных направлений
            for idx, frame in enumerate(direction_frames):
                try:
                    direction_text = frame.text
                    direction_type = "there" if idx == 0 else "back"
                    
                    if status_callback:
                        await status_callback(f"📊 обрабатываю рейсы {direction_text}...")
                    
                    # находим все карточки рейсов для текущего направления
                    parent_frame = frame.find_element(By.XPATH, "./ancestor::div[contains(@class,'frame') and contains(@class,'flight-searchs')]")
                    cards = parent_frame.find_elements(By.XPATH, ".//div[contains(@class,'flight-search') and @tabindex='0']")
                    
                    if not cards:
                        if status_callback:
                            await status_callback(f"ℹ️ не найдено рейсов для направления {direction_text}")
                        results[direction_type] = []
                    else:
                        if status_callback:
                            await status_callback(f"✅ найдено {len(cards)} карточек рейсов для направления {direction_text}")
                            
                        for card_idx, card in enumerate(cards, 1):
                            try:
                                if status_callback:
                                    await status_callback(f"🎫 обрабатываю билет {card_idx}/{len(cards)} для направления {direction_text}...")
                                
                                flight_data = extract_flight_data(card, card_idx, driver, wait)
                                results[direction_type].append(flight_data)
                                
                                if status_callback:
                                    await status_callback(f"✅ билет {card_idx}/{len(cards)} обработан успешно")
                            except Exception as e:
                                if status_callback:
                                    await status_callback(f"⚠️ ошибка при обработке билета {card_idx}: {str(e)}")
                        
                        if status_callback:
                            await status_callback(f"✅ обработано {len(results[direction_type])} рейсов для направления {direction_text}")
                
                except Exception as e:
                    if status_callback:
                        await status_callback(f"⚠️ ошибка при обработке направления {idx}: {str(e)}")
            
            if status_callback:
                await status_callback("✅ обработка результатов завершена")
            
            return results, browser_created_here
            
        except Exception as e:
            if status_callback:
                await status_callback(f"❌ произошла ошибка при обработке результатов: {str(e)}")
            return {"error": f"Results processing error: {str(e)}"}, browser_created_here

    except Exception as e:
        if status_callback:
            await status_callback(f"❌ произошла ошибка при поиске: {str(e)}")
        return {"error": str(e)}, browser_created_here
    finally:
        # Закрываем браузер только если мы его создали в этой функции
        if browser_created_here and driver:
            driver.quit()


async def search_roundtrip(
    from_city, 
    to_city, 
    depart_date, 
    return_date,  # Обязательный параметр для этой функции
    adults_count=1,
    children_count=0,
    class_type="economy", 
    flight_filter="all",
    status_callback=None
):
    """
    Выполняет поиск билетов туда и обратно в одной сессии браузера
    
    Returns:
        dict: результаты поиска для обоих направлений
    """
    combined_results = {"there": [], "back": []}
    driver = None
    wait = None
    
    try:
        # 1. Создаем браузер
        driver, wait = await create_browser()
        
        # 2. Выполняем поиск туда
        if status_callback:
            await status_callback("🔎 Выполняю поиск рейсов ТУДА...")
        
        there_results, _ = await search_flights(
            from_city=from_city,
            to_city=to_city,
            depart_date=depart_date,
            adults_count=adults_count,
            children_count=children_count,
            class_type=class_type,
            flight_filter=flight_filter,
            status_callback=status_callback,
            driver=driver,
            wait=wait
        )
        
        # Проверяем, есть ли ошибка в результатах поиска туда
        if "error" in there_results:
            return there_results  # Возвращаем ошибку, если поиск туда не удался
        
        combined_results["there"] = there_results.get("there", [])
        
        # 3. Выполняем поиск обратно
        if status_callback:
            await status_callback("🔎 Выполняю поиск рейсов ОБРАТНО...")
        
        back_results, _ = await search_flights(
            from_city=to_city,  # Меняем города местами
            to_city=from_city,
            depart_date=return_date,
            adults_count=adults_count,
            children_count=children_count,
            class_type=class_type,
            flight_filter=flight_filter,
            status_callback=status_callback,
            driver=driver,
            wait=wait
        )
        
        if "error" not in back_results:
            combined_results["back"] = back_results.get("there", [])
        
        return combined_results
    
    except Exception as e:
        if status_callback:
            await status_callback(f"❌ Произошла ошибка при выполнении поиска: {str(e)}")
        return {"error": str(e)}
    finally:
        # Закрываем браузер
        if driver:
            driver.quit()


def extract_flight_data(card, card_idx, driver, wait):
    """
    извлекает данные о рейсе из карточки.
    
    Args:
        card: элемент карточки рейса
        card_idx: индекс карточки
        driver: экземпляр WebDriver
        wait: экземпляр WebDriverWait
        
    Returns:
        dict: данные о рейсе
    """
    try:
        print(f"Обрабатываю карточку рейса #{card_idx}")
        
        # определение наличия пересадки
        has_transfer = False
        transfer_time = None
        try:
            transfer_element = card.find_element(By.XPATH, ".//span[contains(text(),'пересадка')]")
            has_transfer = True
            transfer_time = transfer_element.text.replace("пересадка", "").strip()
        except Exception:
            pass
        
        # Также определяем наличие пересадки по количеству сегментов полета
        segments = card.find_elements(By.XPATH, ".//div[contains(@class,'flight-search__flights') and @role='row']")
        valid_segments_count = 0
        for seg in segments:
            # проверяем, является ли этот сегмент информационной строкой о пересадке или дате
            if seg.find_elements(By.XPATH, ".//div[contains(@class,'flight-search__transfer')]"):
                continue  # пропускаем информационные строки
            
            # проверяем наличие информации о вылете/прилете
            time_destination = seg.find_elements(By.XPATH, ".//div[contains(@class,'time-destination__row')]")
            if time_destination:
                valid_segments_count += 1
        
        # Если больше одного сегмента, значит есть пересадки
        if valid_segments_count > 1:
            has_transfer = True
            if transfer_time is None:
                transfer_time = f"{valid_segments_count - 1} пересадка(и)"

        # извлечение количества доступных мест
        seats_left_val = "—"
        try:
            # Ищем элемент с классом flight-search__left в текущей карточке
            seats_elements = card.find_elements(By.XPATH, ".//div[contains(@class,'flight-search__left')]")
            if seats_elements:
                for element in seats_elements:
                    seats_text = element.text
                    if "доступно мест" in seats_text.lower():
                        seats_left_val = extract_seats_text(seats_text)
                        break
        except Exception as e:
            print(f"Ошибка при извлечении количества мест: {e}")
        
        # получение и обработка только валидных сегментов полета
        valid_segments = []
        
        for seg in segments:
            # проверяем, является ли этот сегмент информационной строкой о пересадке или дате
            if seg.find_elements(By.XPATH, ".//div[contains(@class,'flight-search__transfer')]"):
                continue  # пропускаем информационные строки
            
            # проверяем наличие информации о вылете/прилете
            time_destination = seg.find_elements(By.XPATH, ".//div[contains(@class,'time-destination__row')]")
            if not time_destination:
                continue  # пропускаем сегменты без информации о маршруте
            
            # город вылета/прилета
            depart_city = safe_find_text(seg, ".//span[contains(@class,'helptext--left')]")
            arrive_city = safe_find_text(seg, ".//span[contains(@class,'helptext--right')]")
            
            # время вылета
            dep_time = safe_find_text(seg, ".//div[contains(@class,'time-destination__from')]//span[contains(@class,'time-destination__time')]")
            
            # время прилета
            try:
                arr_block = seg.find_element(By.XPATH, ".//div[contains(@class,'time-destination__to')]/div[contains(@class,'time-destination__time')]")
                arr_time = arr_block.find_element(By.XPATH, ".//span").text
                try:
                    plus_day = arr_block.find_element(By.XPATH, ".//span[contains(@class,'time-destination__plusday')]").text
                    arr_time = f"{arr_time} {plus_day}"
                except Exception:
                    pass
            except Exception:
                arr_time = "—"

            # IATA
            try:
                iata_from = seg.find_element(By.XPATH, ".//div[contains(@class,'time-destination__from')]/span[contains(@class,'time-destination__airport')]").text
            except Exception:
                iata_from = "—"
            try:
                iata_to = seg.find_element(By.XPATH, ".//div[contains(@class,'time-destination__to')]/span[contains(@class,'time-destination__airport')]").text
            except Exception:
                iata_to = "—"
            
            # компания и номер, модель
            airline = safe_find_text(seg, ".//div[contains(@class,'flight-search__company-name')]")
            flight_number = safe_find_text(seg, ".//div[contains(@class,'flight-search__plane-number') and not(contains(@class,'hide--above-desktop'))]")
            if flight_number == "—":
                # попробуем получить номер рейса из мобильной версии
                flight_number = safe_find_text(seg, ".//div[contains(@class,'flight-search__plane-number')]")
            
            plane_model = safe_find_text(seg, ".//div[contains(@class,'flight-search__plane-model')]")

            valid_segments.append({
                "depart_city": depart_city,
                "arrive_city": arrive_city,
                "dep_time": dep_time,
                "arr_time": arr_time,
                "iata_from": iata_from,
                "iata_to": iata_to,
                "airline": airline,
                "flight_number": flight_number,
                "plane_model": plane_model
            })

        # извлечение тарифной информации
        miles_cost = "—"
        rubles_cost = "—"
        
        try:
            # нажимаем на кнопку "выбрать рейс" для получения тарифной информации
            choose_button = card.find_element(By.XPATH, ".//button[contains(@class,'button--outline')]")
            driver.execute_script("arguments[0].scrollIntoView(true);", choose_button)
            driver.execute_script("arguments[0].click();", choose_button)
            
            # ожидаем открытия модального окна с тарифами
            time.sleep(2)
            
            # Ограничиваем время на получение тарифа
            try:
                # получаем информацию о тарифе "стандарт"
                miles_cost, rubles_cost = get_tariff_info(driver, wait)
            except Exception as tariff_error:
                print(f"Ошибка при получении данных о тарифе: {tariff_error}")
                miles_cost, rubles_cost = "—", "—"
            
            # ожидаем закрытия модального окна
            time.sleep(1)
            
        except (NoSuchElementException, ElementClickInterceptedException) as e:
            print(f"не удалось получить информацию о тарифе: {e}")
        
        # составляем итоговый результат
        flight_data = {
            "id": card_idx,
            "seats_available": seats_left_val,
            "has_transfer": has_transfer,
            "transfer_time": transfer_time if has_transfer else None,
            "segments": valid_segments,
            "miles_cost": miles_cost,
            "rubles_cost": rubles_cost
        }
        
        print(f"Карточка рейса #{card_idx} успешно обработана")
        return flight_data
        
    except Exception as e:
        print(f"ошибка при извлечении данных о рейсе: {e}")
        # возвращаем пустой объект с базовыми данными вместо None
        return {
            "id": card_idx,
            "error": str(e),
            "segments": [],
            "seats_available": "—",
            "has_transfer": False,
            "miles_cost": "—",
            "rubles_cost": "—"
        }
        
def get_tariff_info(driver, wait):
    """
    извлекает информацию о тарифе "стандарт" из модального окна.
    
    Args:
        driver: экземпляр WebDriver
        wait: экземпляр WebDriverWait
        
    Returns:
        tuple: (стоимость в милях, стоимость в рублях)
    """
    try:
        # ожидаем загрузку модального окна с тарифами
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'tariff__table-price')]")))
        
        # находим информацию о тарифе "стандарт" (второй блок цен)
        standard_tariff = driver.find_elements(By.XPATH, "//div[contains(@class,'tariff__table-cell') and contains(@class,'tariff__table-price')]")[1]
        
        miles_text = ""
        rubles_text = ""
        
        # извлекаем стоимость в милях
        miles_element = standard_tariff.find_element(By.XPATH, ".//div")
        miles_text = miles_element.text.replace("от", "").replace("¥", "").strip()
        miles_match = re.search(r'(\d+\s*\d*)', miles_text)
        if miles_match:
            miles_text = miles_match.group(1).replace(" ", "")
        
        # извлекаем стоимость в рублях
        rubles_element = standard_tariff.find_element(By.XPATH, ".//p[contains(@class,'text--compact')]")
        rubles_text = rubles_element.text
        rubles_match = re.search(r'и\s*(\d+\s*\d*)', rubles_text)
        if rubles_match:
            rubles_text = rubles_match.group(1).replace(" ", "")
        
        # закрываем модальное окно, нажав на крестик или заднюю кнопку
        try:
            close_button = driver.find_element(By.XPATH, "//button[contains(@class,'modal__close')]")
            close_button.click()
        except:
            try:
                back_button = driver.find_element(By.XPATH, "//button[contains(@class,'button--back')]")
                back_button.click()
            except:
                # если не удалось закрыть, нажимаем Escape
                from selenium.webdriver.common.keys import Keys
                webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        
        return miles_text, rubles_text
    except Exception as e:
        print(f"ошибка при получении данных о тарифе: {e}")
        return "—", "—"

def extract_seats_text(text):
    """извлекает количество доступных мест из текста"""
    # Сделаем поиск более гибким, учитывая разные форматы и регистры
    text = text.lower()
    match = re.search(r'доступно\s+мест\s+по\s+текущей\s+цене:\s*(\d+)', text)
    if match:
        return match.group(1)
    
    # Попробуем другие варианты формата
    match = re.search(r'доступно\s+(\d+)\s+мест', text)
    if match:
        return match.group(1)
    
    # Просто найдем числовое значение, если оно есть
    match = re.search(r':\s*(\d+)', text)
    if match:
        return match.group(1)
    
    return "—"

def safe_find_text(el, xpath):
    """безопасно извлекает текст из элемента"""
    try:
        return el.find_element(By.XPATH, xpath).text
    except Exception:
        return "—"