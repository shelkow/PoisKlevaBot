# -*- coding: utf-8 -*-
#!pip install python-telegram-bot --quiet
#!pip install ephem

# @title PROGNOZZZ KLEVA
from pickle import TRUE
import logging
import requests
import ephem
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import timedelta
import os
from bs4 import BeautifulSoup
import re
from datetime import timedelta
import datetime
import asyncio
import pytz

# 🔐 Ключи
import os

BOT_TOKEN = os.getenv('BOT_TOKEN')
OWM_API_KEY = os.getenv('OWM_API_KEY')
LOCATION = 'Kaluga,RU'
# 🔥 Давление вчера в Калуге
def get_yesterday_pressure(latitude=54.51, longitude=36.26):
    yesterday = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).date()
    start = yesterday.isoformat()
    end = yesterday.isoformat()
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}&"
        f"start_date={start}&end_date={end}&"
        f"hourly=pressure_msl&timezone=Europe/Moscow"
    )
    response = requests.get(url)
    data = response.json()
    pressures = data.get('hourly', {}).get('pressure_msl', [])
    times = data.get('hourly', {}).get('time', [])
    if not pressures or not times:
        return None
    # Найдём индекс времени 12:00 МСК
    try:
        index = times.index(f"{yesterday}T12:00")
        pressure_noon_msk = pressures[index]
        return pressure_noon_msk
    except ValueError:
        # Если по какой-то причине времени 12:00 нет в данных
        # вернём среднее за день
        avg_pressure = sum(pressures) / len(pressures)
        return avg_pressure

# 🔥 Функция определения ночи
def is_day():
        kaluga = ephem.Observer()
        kaluga.lat, kaluga.lon = '54.51', '36.25'
        kaluga.date = ephem.now()

        sunset_prev = kaluga.previous_setting(ephem.Sun()).datetime()
        sunrise_next = kaluga.next_rising(ephem.Sun()).datetime()
        now_utc = datetime.datetime.utcnow()
        if sunset_prev <= now_utc < sunrise_next:
          condition = False
        else:
          condition=True

        return condition
# 🔥 Рассчитываем индекс геомагнитных излучений
def get_kp_index():
    kp_url = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
    try:
        response = requests.get(kp_url)
        data = response.json()
        current_kp_raw = data[-1]['kp']

        base_str = re.findall(r'\d+', current_kp_raw)
        if not base_str:
            return current_kp_raw, "не удалось распознать"
        base_val = float(base_str[0])

        if 'M' in current_kp_raw:
            kp_value = base_val + 0.5
        elif '+' in current_kp_raw:
            kp_value = base_val + 0.33
        elif '-' in current_kp_raw:
            kp_value = base_val - 0.33
        else:
            kp_value = base_val

        if kp_value <= 3:
            desc = "Спокойная геомагнитная обстановка \n Хорошие условия для рыбалки."
        elif 4 <= kp_value <= 5:
            desc = "Слабая геомагнитная активность \n Возможны небольшие помехи, рыба может вести себя нестабильно."
        elif 6 <= kp_value <= 7:
            desc = "Умеренная геомагнитная буря \n Клёв может быть слабым."
        else:
            desc = "Сильная геомагнитная буря \n Плохие условия, рыба пассивна."

        return f"({kp_value:.2f})", desc
    except Exception:
        return "нет данных", "ошибка получения"

# 🔥 Рассчитываем индекс ультрафиолета в Калуге
def get_uv_index(lat=54.51, lon=36.25):
    try:
        tz = pytz.timezone("Europe/Moscow")
        now = datetime.datetime.now(tz).replace(minute=0, second=0, microsecond=0)
        now_iso = now.isoformat()

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&hourly=uv_index"
            f"&timezone=auto"
        )

        response = requests.get(url)
        response.raise_for_status()  # проверка HTTP ошибки
        data = response.json()

        times = data.get('hourly', {}).get('time', [])
        uvs = data.get('hourly', {}).get('uv_index', [])

        if not times or not uvs:
            return None, "Данные по UV-индексу отсутствуют."

        # ищем индекс текущего часа
        if now_iso in times:
            index = times.index(now_iso)
            uv_now = uvs[index]
        else:
            uv_now = max(uvs)  # максимум за день

        if uv_now < 2:
            desc = "Низкий UV-индекс. Безопасно, но рыба может быть менее активна."
        elif 2 <= uv_now < 5:
            desc = "Умеренный UV-индекс. Хорошие условия для рыбалки."
        elif 5 <= uv_now < 7:
            desc = "Высокий UV-индекс. Будьте осторожны, рыба в ахуе и скорее всего на дне."
        elif 7 <= uv_now < 10:
            desc = "Очень высокий UV-индекс. Возможен солнечный ожог, рыба на дне."
        else:
            desc = "Экстремальный UV-индекс. Лучше избегать солнца."

        return uv_now, desc

    except requests.RequestException as e:
        return None, f"Ошибка запроса: {e}"
    except Exception as e:
        return None, f"Ошибка обработки данных: {e}"


kp_value, kp_desc = get_kp_index()
uv_value, uv_desc = get_uv_index()

# 🔥 Функция парсинга температуры воды в Калуге)
def get_water_temp():
    url = "https://seatemperatures.net/asia/russia/oka-river-near-kaluga/"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Ищем <p> с температурой воды
        temp_tag = soup.find("p", class_="temperature is-size-2 mb-0 has-text-weight-medium")
        if temp_tag:
            temp_text = temp_tag.text.strip()
            temp_value = float(temp_text.replace("° C", "").strip())
            return temp_value
    except Exception as e:
        logging.warning(f"Ошибка парсинга температуры воды: {e}")
    return None

# 🌗 🔥 Влияние фазы луны на рыбалку
def get_moon_phase():
    new_moon = ephem.previous_new_moon(ephem.now())
    moon_age_days = ephem.now() - new_moon  # float

    if moon_age_days < 1:
        phase_name = "🌑 Новолуние ❌ "
        score = 0
        max_score = 10
    elif 1 <= moon_age_days < 7:
        phase_name = "🌒 Растущая Луна 🟡"
        score = 7
        max_score = 10
    elif 7 <= moon_age_days < 8:
        phase_name = "🌓 Первая четверть ✅ "
        score = 10
        max_score = 10
    elif 8 <= moon_age_days < 14:
        phase_name = "🌔 Прибывающая Луна 🟡"
        score = 7
        max_score = 10
    elif 14 <= moon_age_days < 15:
        phase_name = "🌕 Полнолуние ❌"
        score = 0
        max_score = 10
    elif 15 <= moon_age_days < 21:
        phase_name = "🌔 Убывающая Луна 🟡"
        score = 4
        max_score = 10
    elif 21 <= moon_age_days < 22:
        phase_name = "🌗 Последняя четверть ❌"
        score = 2
        max_score = 10
    elif 22 <= moon_age_days <= 29.53:
        phase_name = "🌘 Старая Луна 🟡"
        score = 5
        max_score = 10
    else:
        phase_name = "Неизвестная фаза"
        score = 0
        max_score = 10
  # Добавляем корректировку для хорошего клёва с 18 по 22 день
    if 18 <= moon_age_days <= 22:
        phase_name += " (Хороший клёв 👍)"
        score = max(score, 8)  # повышаем оценку клёва
    if 3 <= moon_age_days <= 10:
        phase_name += " (Хороший клёв 👍)"
        score = max(score, 10)  # повышаем оценку клёва
    return f"{phase_name} {moon_age_days:.2f}", score, max_score

# 🔥 Запрос параметров о погоде с API
def get_weather():
    url = f"http://api.openweathermap.org/data/2.5/weather?q={LOCATION}&appid={OWM_API_KEY}&units=metric"
    res = requests.get(url).json()
    pressure_hpa = res['main']['pressure']
    pressure_mmhg = round(pressure_hpa / 1.333, 1)
    weather_id = res['weather'][0]['id']

    weather = {
        'temp': res['main']['temp'],
        'pressure': pressure_mmhg,
        'wind_speed': res['wind']['speed'],
        'wind_deg': res['wind']['deg'],
        'desc': res['weather'][0]['description'],
        'clouds': res['clouds']['all'],  # %
        'humidity': res['main']['humidity'],  # ← Влажность
        'weather_id': weather_id

    }

    return weather
# 🔥 Прогноз на завтра, послезавтра
def get_weather_forecast(days_ahead=1):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={LOCATION}&appid={OWM_API_KEY}&units=metric"
    res = requests.get(url).json()
    forecast_list = res.get('list', [])
    # Смещение для Москвы: UTC+3
    MSK_OFFSET = 3
    # Целевая дата в МСК с учётом days_ahead
    now_utc = datetime.datetime.utcnow()
    now_msk = now_utc + datetime.timedelta(hours=MSK_OFFSET)
    target_date = (now_msk + datetime.timedelta(days=days_ahead)).date()
    for entry in forecast_list:
        dt_txt = entry['dt_txt']  # в UTC, например "2025-06-21 12:00:00"
        dt_utc = datetime.datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
        # Переводим в МСК
        dt_msk = dt_utc + datetime.timedelta(hours=MSK_OFFSET)
        # Проверяем дату и время по МСК
        #if dt_msk.date() == target_date and dt_msk.hour == 9:
        if dt_msk.date() == target_date and dt_msk.hour == 12:
        #if dt_msk.date() == target_date and dt_msk.hour == 15:
        #if dt_msk.date() == target_date and dt_msk.hour == 18:
        #if dt_msk.date() == target_date and dt_msk.hour == 21:
            pressure_hpa = entry['main']['pressure']
            pressure_mmhg = round(pressure_hpa / 1.333, 1)
            weather = {
                'temp': entry['main']['temp'],
                'pressure': pressure_mmhg,
                'wind_speed': entry['wind']['speed'],
                'wind_deg':  entry['wind']['deg'],
                'desc': entry['weather'][0]['description'],
                'clouds': entry['clouds']['all'],
                'humidity': entry['main']['humidity'],
                'weather_id': entry['weather'][0]['id']
            }
            return weather

    return None  # если не нашли нужный прогноз
# 🔥 Интерпретация направления ветра
def wind_deg_to_short(deg):
    directions = [
        "С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ",
        "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"
    ]
    ix = int((deg + 11.25) % 360 / 22.5)
    return directions[ix]
# 🔥 Итоговая функция рассчета клева
def calculate_klev_score(weather, moon_score,water_temp=None):
    score = moon_score
    details = {}

    # Луна
    moon_max = 10
    details['Луна'] = (moon_score, moon_max)

    pressure_today = weather['pressure'] - 18  # Текущее давление с корректировкой
    pressure_yesterday = get_yesterday_pressure()  # Функция или переменная с давлением вчера
    pressure_yesterday = (pressure_yesterday * 0.75006)-18
    diff = abs(pressure_today - pressure_yesterday)

    if diff > 10:
        pressure_score = 3  # Перепад больше 10 мм — плохо
    elif 4 < diff <= 10:
        pressure_score = 5  # Перепад от 5 до 10 мм — средне
    elif 1 < diff <= 5:
        pressure_score = 8  # Перепад от 2 до 5 мм — почти стабильно
    else:  # diff <= 2
        pressure_score = 10  # Перепад 0-2 мм — отлично, стабильное давление

    details['Давление'] = (pressure_score, 10)
    score += pressure_score

    # Ветер
    wind_score = 0
    wind_speed = weather['wind_speed']  # в м/с
    wind_d = weather['wind_deg']  # в м/с

    wdres=wind_deg_to_short(wind_d)
    windkm = wind_speed * 3.6           # перевод в км/ч

    if windkm < 5:
        wind_score = 7  # Почти штиль — идеально
    elif 5 <= windkm < 10:
        wind_score = 10   # Лёгкий ветер — хорошо
    elif 10 <= windkm < 15:
        wind_score = 9   # Умеренный ветер — сносно
    elif 15 <= windkm < 20:
        wind_score = 5   # Сильный ветер — клёв ухудшается
    elif 20 <= windkm < 25:
        wind_score = 3   # Очень сильный ветер — плохо
    else:  # 25 и выше
        wind_score = 1   # Штормовой ветер — почти невозможно

    details['Ветер'] = (wind_score, 10)
    details['Направление'] = wdres

    score += wind_score

    # Облачность с учётом времени заката
    cloud_score = 0
    clouds = weather['clouds']

    if is_day():
        cloud_score = 10  # ночью все равно на облачность
    else:
        if 50 <= clouds <= 100:
            cloud_score = 10
        elif 30 <= clouds < 50:
            cloud_score = 7
        elif 10 <= clouds < 30:
            cloud_score = 5
        else:
            cloud_score = 1

    details['Облачность'] = (cloud_score, 10)
    score += cloud_score


    # Влажность
    humidity_score = 0
    humidity = weather['humidity']

    if 80 <= humidity <= 100:
        humidity_score = 10  # Идеальные условия
    elif 50 <= humidity < 80:
        humidity_score = 8   # Хорошие условия
    elif 30 <= humidity < 50:
        humidity_score = 5   # Умеренные/плохие условия
    else:  # humidity <30
        humidity_score = 2   # Слишком сухо

    details['Влажность'] = (humidity_score, 10)
    score += humidity_score


    # Основной код оценки осадков
    precip_score = 0
    weather_id = weather['weather_id']
    print(f"Debug: weather_id = {weather_id}")

    if 200 <= weather_id < 233:
        precip_score = 0
        precip_desc = "Гроза и гром"
    elif 300 <= weather_id < 322:
        precip_score = 7
        precip_desc = "Небольшой дождь"
    elif 500 <= weather_id < 532:
        precip_score = 3
        precip_desc = "Дождь"
    elif 600 <= weather_id < 623:
        precip_score = 0
        precip_desc = "Снег"
    elif 701 <= weather_id < 782:
        precip_score = 0
        precip_desc = "Туман, песок, торнадо"
    elif 801 <= weather_id < 805:
        precip_score = 10
        precip_desc = "Облачно"
    elif weather_id == 800:
        if is_day():
            precip_score = 10  # Ночь, чистое небо — отлично
            precip_desc = "Чистое небо (ночь)"
        else:
            precip_score = 6  # День, чистое небо — не идеально
            precip_desc = "Чистое небо (день)"
    else:
        precip_score = 10
        precip_desc = "Нет осадков " + str(weather_id)

    details['Осадки'] = (precip_score, 10, precip_desc)
    score += precip_score

    # Оценка по температуре воды
    water_temp_score = 0
    if water_temp is not None:
        # Пример простых правил оценки температуры воды
        if 15 <= water_temp <= 20:
            water_temp_score = 10
        elif 10 <= water_temp < 15 or 20 < water_temp <= 22:
            water_temp_score = 7
        elif 7 <= water_temp < 10 or 22 < water_temp <= 25:
            water_temp_score = 3
        else:
            water_temp_score = 1
    details['Температура воды'] = (water_temp_score, 10)
    score += water_temp_score

    total_score = max(1, min(100, score))
    return total_score, details, precip_desc, precip_score

def get_best_fishing_time():
    kaluga = ephem.Observer()
    kaluga.lat, kaluga.lon = '54.51', '36.25'
    kaluga.date = ephem.now()

    sunrise_utc = kaluga.next_rising(ephem.Sun()).datetime()
    sunset_utc = kaluga.next_setting(ephem.Sun()).datetime()

    # Смещение для Московского времени (Калуга UTC+3)
    UTC_OFFSET = timedelta(hours=3)

    sunrise_local = sunrise_utc + UTC_OFFSET
    sunset_local = sunset_utc + UTC_OFFSET

    morning = f"{(sunrise_local - timedelta(hours=1)).strftime('%H:%M')}–{(sunrise_local + timedelta(hours=1)).strftime('%H:%M')}"
    evening = f"{(sunset_local - timedelta(hours=1.5)).strftime('%H:%M')}–{(sunset_local + timedelta(hours=0.5)).strftime('%H:%M')}"

    return morning, evening

def get_klev_rating_text(score, max_score=10):
    if score <= 2:
        return f"Очень плохой ({score} из {max_score}) 💀"
    elif 2 < score <= 4:
        return f"Плохой ({score} из {max_score}) 😕"
    elif 4 < score <= 6:
        return f"Средний ({score} из {max_score}) 😐"
    elif 6 < score <= 8:
        return f"Хороший ({score} из {max_score}) 🙂"
    else :  # >8
        return f"Отличный ({score} из {max_score}) 😃"


async def klev_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE, days_ahead=0):
    if days_ahead == 0:
        weather = get_weather()
    else:
        weather = get_weather_forecast(days_ahead)

    water_temp = get_water_temp()
    moon_desc, moon_score, moon_max = get_moon_phase()
    klev_score, breakdown, precip_desc, precip_score = calculate_klev_score(weather, moon_score, water_temp)
    normalized_klev_score = round(klev_score / 70 * 10, 1)
    morning, evening = get_best_fishing_time()

    precip_score, precip_max, precip_desc = breakdown.get('Осадки', (0, 10, 'Нет данных'))

    def format_points(points, maximum):
        return f"({points} из {maximum})"

    water_temp_str = f"{water_temp}°C" if water_temp is not None else "Нет данных"

    reply = (
        f"📍 Калуга\n"
        f"☁️ Погода ({'сегодня' if days_ahead == 0 else f'через {days_ahead} дн.'}): {weather['desc'].capitalize()}, {weather['temp']}°C "
        f"({precip_desc}, {format_points(precip_score, 10)})\n"
        f"💨 Ветер: {weather['wind_speed'] * 3.6:.1f} км/ч {format_points(*breakdown['Ветер'])}\n"
        f"↖️ Направление: {wind_deg_to_short(weather['wind_deg'])}\n"
        f"📉 Давление: {weather['pressure'] - 18:.1f} мм рт. ст. {format_points(*breakdown['Давление'])}\n"
        f"☁️ Облачность: {weather['clouds']}% {format_points(*breakdown['Облачность'])}\n"
        f"{moon_desc} {format_points(*breakdown['Луна'])}\n"
        f"💧 Влажность: {weather['humidity']}% {format_points(*breakdown['Влажность'])}\n"
        f"🌡 Температура воды: {water_temp_str} {format_points(*breakdown['Температура воды'])}\n"
        f"🌍 Геомагнитная активность (Kp): {(kp_value)}\n {kp_desc}\n"
        f"☀️ UV-индекс: {uv_value}\n {uv_desc}\n\n"
        f"🎣 Прогноз клёва: {get_klev_rating_text(normalized_klev_score)}\n"
        f"🕓 Лучшее время:\n Утро {morning} \n Вечер {evening}"
    )
    await update.message.reply_text(reply)
# 🔁 /klev — прогноз на сегодня
async def klev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await klev_forecast(update, context, days_ahead=0)

# 🔁 /klev_zavtra — прогноз на завтра
async def klev_zavtra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await klev_forecast(update, context, days_ahead=1)

# 🔁 /klev_poslezavtra — прогноз на послезавтра
async def klev_poslezavtra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await klev_forecast(update, context, days_ahead=2)

# 🔁 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши /klev чтобы узнать прогноз клёва в Калуге 🎣")

# 🛑 /stop
#async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    await update.message.reply_text("🛑 Бот останавливается...")
#    os._exit(0)  # немедленный выход из процесса
# 👇 Запуск


async def main():
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("klev", klev))
    app.add_handler(CommandHandler("klev_zavtra", klev_zavtra))
    app.add_handler(CommandHandler("klev_poslezavtra", klev_poslezavtra))
    #app.add_handler(CommandHandler("stop", stop))

    print("Бот запущен...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

# ✅ Вызов
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
