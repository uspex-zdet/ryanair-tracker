import time
import csv
import random
import matplotlib.pyplot as plt
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import os
import logging
import serpapi
from datetime import datetime
import pytz

# Установка часового пояса Ирландии
timezone = pytz.timezone('Europe/Dublin')

# Кастомный форматтер для logging с часовым поясом
class LocalTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, timezone)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]

# Настройка логирования с часовым поясом Ирландии
formatter = LocalTimeFormatter(
    fmt='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
handler = logging.FileHandler('/app/data/google_flights_tracker.log', encoding='utf-8')
handler.setFormatter(formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler, stream_handler]
)

# Переменные окружения для email и SerpAPI
EMAIL_SENDER = 'olenaolena2124@gmail.com'
EMAIL_RECEIVER = 'olenaolena2124@gmail.com'
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'ruozcfrazohlwtjw')
SERPAPI_KEY = os.getenv('SERPAPI_KEY')

# Константы
CSV_FILE = '/app/data/google_flights_prices.csv'
PLOT_DIR = '/app/data/price_plots'
HTML_DIR = '/app/data/html_dumps'
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

# Направления и даты
FLIGHTS = [
    {'origin': 'DUB', 'destination': 'LUZ', 'date': '2025-07-17', 'description': 'Dublin-Lublin'},
    {'origin': 'LUZ', 'destination': 'DUB', 'date': '2025-08-10', 'description': 'Lublin-Dublin'},
    {'origin': 'RZE', 'destination': 'DUB', 'date': '2025-08-13', 'description': 'Rzeszow-Dublin'},
]

# Инициализация CSV
def init_csv():
    logging.info("Initializing CSV file")
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Flight', 'Date', 'Price', 'Adjusted_Price', 'Details'])

# Получение цены через SerpAPI с корректировкой
def get_flight_price_serpapi(flight, retries=3, delay=3):
    for attempt in range(retries):
        try:
            logging.info(f"Starting attempt {attempt + 1}/{retries} for {flight['description']}")
            if not SERPAPI_KEY:
                logging.error("SERPAPI_KEY not set")
                return "API error", "API error", "No details"

            params = {
                "api_key": SERPAPI_KEY,
                "engine": "google_flights",
                "departure_id": flight['origin'],
                "arrival_id": flight['destination'],
                "outbound_date": flight['date'],
                "hl": "en",
                "gl": "ie",
                "type": 2,  # 1 for round-trip, 2 for one-way
                "no_cache": True  # Отключаем кэш для актуальных данных
            }
            logging.info(f"Requesting SerpAPI with params: {params}")
            results = serpapi.search(params)
            
            # Преобразуем SerpResults в словарь
            results_dict = results.as_dict() if hasattr(results, 'as_dict') else dict(results)
            
            # Сохранение полного ответа для отладки
            result_path = os.path.join(HTML_DIR, f"{flight['description']}_{flight['date']}_attempt{attempt}.json")
            logging.info(f"Saving API response to {result_path}")
            with open(result_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(results_dict, f, indent=2)
            
            logging.info(f"Full API response keys: {results_dict.keys()}")
            if "error" in results_dict:
                logging.error(f"SerpAPI error: {results_dict['error']}")
                return "API error", "API error", f"Error: {results_dict.get('error', 'Unknown')}"
            
            # Извлечение цены и деталей
            if "best_flights" in results_dict and results_dict["best_flights"]:
                flight_info = results_dict["best_flights"][0]
                price = flight_info.get("price")
                if not price:
                    logging.warning("No price found in best_flights")
                    return "No price found", "No price found", "No details"
                airline = flight_info["flights"][0].get("airline", "Unknown") if "flights" in flight_info else "Unknown"
                stops = len(flight_info.get("flights", [{}])) - 1 if "flights" in flight_info else 0
                details = f"Airline: {airline}, Stops: {stops}"
                # Корректировка цены на ~13% меньше (коэффициент 0.88)
                price_str = str(price)  # Преобразуем цену в строку
                if price_str.replace('€', '').replace('.', '').isdigit():
                    adjusted_price = f"€{int(float(price_str) * 0.88)}"
                else:
                    adjusted_price = "N/A"
                logging.info(f"Price for {flight['description']}: €{price}, Adjusted Price: {adjusted_price}, {details}")
                return f"€{price}", adjusted_price, details
            elif "other_flights" in results_dict and results_dict["other_flights"]:
                flight_info = results_dict["other_flights"][0]
                price = flight_info.get("price")
                if not price:
                    logging.warning("No price found in other_flights")
                    return "No price found", "No price found", "No details"
                airline = flight_info["flights"][0].get("airline", "Unknown") if "flights" in flight_info else "Unknown"
                stops = len(flight_info.get("flights", [{}])) - 1 if "flights" in flight_info else 0
                details = f"Airline: {airline}, Stops: {stops}"
                # Корректировка цены на ~13% меньше (коэффициент 0.88)
                price_str = str(price)  # Преобразуем цену в строку
                if price_str.replace('€', '').replace('.', '').isdigit():
                    adjusted_price = f"€{int(float(price_str) * 0.88)}"
                else:
                    adjusted_price = "N/A"
                logging.info(f"Price for {flight['description']}: €{price}, Adjusted Price: {adjusted_price}, {details}")
                return f"€{price}", adjusted_price, details
            else:
                logging.info(f"No flights found for {flight['description']} on {flight['date']}")
                return "No flights available", "No flights available", "No details"
            
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(delay)
            continue
    
    logging.warning(f"No price found after all retries for {flight['description']}")
    return "No price found", "No price found", "No details"

# Визуализация данных
def plot_prices():
    try:
        logging.info("Starting to plot prices")
        print("Starting to plot prices")
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE, on_bad_lines='skip')  # Игнорируем строки с ошибками
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            for flight in FLIGHTS:
                flight_data = df[df['Flight'] == flight['description']]
                if not flight_data.empty:
                    plt.figure(figsize=(10, 6))
                    # Проверяем, есть ли столбец Adjusted_Price
                    if 'Adjusted_Price' in flight_data.columns:
                        prices = pd.to_numeric(flight_data['Adjusted_Price'].str.replace('€|zŁ', '', regex=True), errors='coerce')
                    else:
                        prices = pd.to_numeric(flight_data['Price'].str.replace('€|zŁ', '', regex=True), errors='coerce')
                    valid_data = flight_data[prices.notna()]
                    if not valid_data.empty:
                        plt.plot(valid_data['Timestamp'], prices[prices.notna()], marker='o', label=flight['description'])
                        plt.title(f'Price Changes for {flight["description"]} ({flight["date"]})')
                        plt.xlabel('Timestamp')
                        plt.ylabel('Price (€)')
                        plt.grid(True)
                        plt.legend()
                        plt.xticks(rotation=45)
                        plt.tight_layout()
                        plot_path = os.path.join(PLOT_DIR, f'{flight["description"]}_{flight["date"]}.png')
                        plt.savefig(plot_path)
                        plt.close()
                        logging.info(f"Plot saved: {plot_path}")
                    else:
                        logging.warning(f"No valid price data for {flight['description']}")
        logging.info("Plots updated")
        print("Finished plotting prices")
    except Exception as e:
        logging.error(f"Error plotting prices: {e}")
        print(f"Error plotting prices: {e}")

# Отправка email
def send_email(prices, last_prices):
    try:
        logging.info("Starting to send email")
        print("Starting to send email")
        body = "Google Flights price changes:\n\n"
        send = False
        for price_info in prices:
            flight = price_info['flight']
            price = price_info['price']
            adjusted_price = price_info['adjusted_price']
            details = price_info['details']
            last_price = last_prices.get(flight, {}).get('adjusted_price', None)
            logging.info(f"Comparing prices for {flight}: current={adjusted_price}, last={last_price}")
            if last_price and last_price != adjusted_price and adjusted_price not in ["No price found", "API error", "No flights available", "N/A"]:
                body += f"{flight} on {price_info['date']}: {adjusted_price} (was {last_price}), Original: {price}, {details}\n"
                send = True
        if send:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_SENDER
            msg['To'] = EMAIL_RECEIVER
            msg['Subject'] = 'Google Flights Price Change Alert'
            msg.attach(MIMEText(body, 'plain'))
            plot_dir_abs = os.path.abspath(PLOT_DIR)
            logging.info(f"Checking plots in directory: {plot_dir_abs}")
            for flight in FLIGHTS:
                plot_path = os.path.join(PLOT_DIR, f'{flight["description"]}_{flight["date"]}.png')
                plot_path_abs = os.path.abspath(plot_path)
                logging.info(f"Checking plot: {plot_path_abs}")
                if os.path.exists(plot_path_abs):
                    with open(plot_path_abs, 'rb') as f:
                        img = MIMEImage(f.read())
                        img.add_header('Content-Disposition', f'attachment; filename={os.path.basename(plot_path)}')
                        msg.attach(img)
                        logging.info(f"Attached plot: {plot_path_abs}")
                else:
                    logging.info(f"Plot not found: {plot_path_abs}")
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
            logging.info("Email sent successfully")
            print("Email sent successfully")
        else:
            logging.info("No price changes, email not sent")
            print("No price changes, email not sent")
    except Exception as e:
        logging.error(f"Error sending email: {e}")
        print(f"Error sending email: {e}")

# Сбор цен
def collect_prices():
    timestamp = datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S')
    logging.info(f"Collecting prices at {timestamp}")
    print(f"Collecting prices at {timestamp}")
    last_prices = {}
    try:
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE, on_bad_lines='skip')  # Игнорируем строки с ошибками
            last_prices = df.groupby('Flight').last().to_dict('index')
            logging.info(f"Loaded last prices: {last_prices}")
            print(f"Loaded last prices: {last_prices}")
    except Exception as e:
        logging.error(f"Error loading last prices: {e}")
        print(f"Error loading last prices: {e}")

    prices = []
    for flight in FLIGHTS:
        price, adjusted_price, details = get_flight_price_serpapi(flight)
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, flight['description'], flight['date'], price, adjusted_price, details])
        prices.append({
            'flight': flight['description'],
            'date': flight['date'],
            'price': price,
            'adjusted_price': adjusted_price,
            'details': details
        })
        logging.info(f"{flight['description']} on {flight['date']}: {price}, Adjusted: {adjusted_price}, {details}")
        print(f"{flight['description']} on {flight['date']}: {price}, Adjusted: {adjusted_price}, {details}")
        time.sleep(random.uniform(3, 6))

    plot_prices()
    send_email(prices, last_prices)
    logging.info("Price collection completed")
    print("Price collection completed")

def main():
    init_csv()
    collect_prices()

if __name__ == '__main__':
    main()