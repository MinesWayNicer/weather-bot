import requests
import time   # <-- for sleep between API calls

subscribers = set()  # <--(global storage for chat IDs)
# =========================
# CONFIG
# =========================
import os


BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

import time

# =========================================================
# 🧠 USER STATE STORAGE
# ---------------------------------------------------------
# This keeps track of each user (chat_id):
# - what city they asked for
# - whether they're subscribed to updates
# - when their subscription expires (24h rule)
# =========================================================
user_state = {}

# Telegram update pointer (prevents duplicate processing)
offset = None


# =========================================================
# 🌍 GEOCODING (city → coordinates)
# ---------------------------------------------------------
# Converts a city name into latitude/longitude using Open-Meteo
# Needed because weather API requires coordinates, not names
# =========================================================
def geocode_city(city: str):
    url = "https://geocoding-api.open-meteo.com/v1/search"

    try:
        r = requests.get(url, params={"name": city, "count": 1})
        data = r.json()

        if "results" not in data or not data["results"]:
            return None

        place = data["results"][0]

        return {
            "name": place["name"],
            "lat": place["latitude"],
            "lon": place["longitude"],
            "country": place.get("country")
        }

    except:
        return None


# =========================================================
# 🌦 CURRENT WEATHER FETCH
# ---------------------------------------------------------
# Gets live weather data for a given lat/lon
# =========================================================
def get_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": True,
        "timezone": "auto"
    }

    r = requests.get(url, params=params)
    return r.json().get("current_weather")


# =========================================================
# 📊 24-HOUR FORECAST
# ---------------------------------------------------------
# Returns hourly temperature data for 1 day
# Used after user says "y"
# =========================================================
def get_24h_forecast(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m",
        "forecast_days": 1,
        "timezone": "auto"
    }

    r = requests.get(url, params=params)
    return r.json().get("hourly", {})


# =========================================================
# 📡 TELEGRAM: FETCH NEW MESSAGES
# ---------------------------------------------------------
# Pulls new messages from Telegram API
# offset prevents processing same message twice
# =========================================================
def get_updates():
    global offset

    r = requests.get(
        f"{BASE_URL}/getUpdates",
        params={"timeout": 100, "offset": offset}
    )

    return r.json()["result"]


# =========================================================
# 📤 TELEGRAM: SEND MESSAGE
# ---------------------------------------------------------
# Sends text back to user via Telegram
# =========================================================
def send_message(chat_id, text):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )


# =========================================================
# 🧾 FORMAT WEATHER OUTPUT
# ---------------------------------------------------------
# Turns raw API data into human-readable message
# =========================================================
def format_weather(location, weather):
    return (
        f"📍 {location['name']}, {location.get('country','')}\n"
        f"🌡 {weather['temperature']}°C\n"
        f"💨 {weather['windspeed']} km/h\n"
        f"🕒 {weather['time']}"
    )


# =========================================================
# 🚀 MAIN BOT LOOP
# ---------------------------------------------------------
# Runs forever:
# 1. checks for new messages
# 2. responds to commands
# 3. handles subscriptions
# =========================================================
print("Smart weather bot running...")

while True:
    updates = get_updates()

    # -----------------------------------------------------
    # 💬 PROCESS USER MESSAGES
    # -----------------------------------------------------
    for update in updates:
        offset = update["update_id"] + 1

        message = update.get("message", {})
        text = message.get("text", "").lower().strip()
        chat_id = message.get("chat", {}).get("id")

        if not text or not chat_id:
            continue

        # Save that this user exists (for future updates)
        user_state.setdefault(chat_id, {})

        # -------------------------------------------------
        # STEP 1: USER REQUESTS WEATHER
        # -------------------------------------------------
        if text.startswith("weather"):
            city = text.replace("weather", "").strip() or "Kingston"

            location = geocode_city(city)
            if not location:
                send_message(chat_id, "City not found")
                continue

            weather = get_weather(location["lat"], location["lon"])
            if not weather:
                send_message(chat_id, "Weather error")
                continue

            # Store user session data
            user_state[chat_id] = {
                "city": city,
                "lat": location["lat"],
                "lon": location["lon"],
                "subscribed": False,
                "expires_at": time.time() + 86400  # 24 hours
            }

            send_message(chat_id, format_weather(location, weather))
            send_message(chat_id, "Want 24h forecast + hourly updates? (y/n)")
            continue

        # -------------------------------------------------
        # STEP 2: USER ACCEPTS SUBSCRIPTION
        # -------------------------------------------------
        if text == "y" and chat_id in user_state:
            state = user_state[chat_id]

            forecast = get_24h_forecast(state["lat"], state["lon"])
            temps = forecast.get("temperature_2m", [])[:6]

            msg = f"📊 24h Forecast for {state['city']}:\n"
            for i, t in enumerate(temps):
                msg += f"+{i}h: {t}°C\n"

            send_message(chat_id, msg)
            send_message(chat_id, "Subscribed for 24h hourly updates ⏳")

            state["subscribed"] = True
            continue

        # -------------------------------------------------
        # DEFAULT RESPONSE
        # -------------------------------------------------
        send_message(chat_id, "Send: weather <city>")

    # -----------------------------------------------------
    # ⏰ BACKGROUND SUBSCRIPTION ENGINE
    # -----------------------------------------------------
    now = time.time()

    for chat_id in list(user_state.keys()):
        state = user_state[chat_id]

        # Remove expired users after 24h
        if now > state["expires_at"]:
            send_message(chat_id, "Subscription expired ⏳")
            del user_state[chat_id]
            continue

        # Send hourly updates if subscribed
        if state.get("subscribed"):
            location = geocode_city(state["city"])

            if location:
                weather = get_weather(location["lat"], location["lon"])
                send_message(chat_id, "Hourly update:\n" + format_weather(location, weather))# deploy fix
# force redeploy
