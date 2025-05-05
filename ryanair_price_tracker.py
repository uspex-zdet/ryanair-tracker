import requests
import csv
import time
from datetime import datetime
import logging
import random
import matplotlib.pyplot as plt
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import os

# Настройка логирования с поддержкой UTF-8
logging.basicConfig(
    filename='/app/data/ryanair_price_tracker.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# Заголовки для API Ryanair
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.ryanair.com/gb/en',
    'Connection': 'keep-alive',
}

# Список User-Agent для ротации
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
]

# Направления и даты
FLIGHTS = [
    {'origin': 'DUB', 'destination': 'LUZ', 'date': '2025-07-17', 'description': 'Dublin-Lublin'},
    {'origin': 'LUZ', 'destination': 'DUB', 'date': '2025-08-10', 'description': 'Lublin-Dublin'},
    {'origin': 'RZE', 'destination': 'DUB', 'date': '2025-08-13', 'description': 'Rzeszow-Dublin'},
]

# CSV-файл и папка для графиков
CSV_FILE = '/app/data/ryanair_prices.csv'
PLOT_DIR = '/app/data/price_plots'
os.makedirs(PLOT_DIR, exist_ok=True)

# Email настройки (значения будут браться из переменных окружения)
EMAIL_SENDER = 'olenaolena2124@gmail.com'
EMAIL_RECEIVER = 'olenaolena2124@gmail.com'
EMAIL_PASSWORD = 'ruozcfrazohlwtjw'
# EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')  # Пароль из переменной окружения

# Курс PLN к EUR
PLN_TO_EUR = 0.23

# Инициализация CSV-файла
def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Flight', 'Date', 'Price'])

# Получение цены через API Ryanair
def get_flight_price_api(flight, retries=3, delay=5):
    url = f"https://www.ryanair.com/api/booking/v4/en-gb/availability?Origin={flight['origin']}&Destination={flight['destination']}&DateOut={flight['date']}&FlexDaysOut=0&ADT=1&CHD=0&INF=0&TEEN=0&RoundTrip=false&ToUs=AGREED"
    headers = HEADERS.copy()
    headers['User-Agent'] = random.choice(USER_AGENTS)
    session = requests.Session()
    try:
        session.get('https://www.ryanair.com/gb/en', headers=headers)
        for attempt in range(retries):
            try:
                print(f"Attempting API request for {flight['description']} (attempt {attempt + 1}/{retries})")
                response = session.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                logging.info(f"API response for {flight['description']}: {data}")
                if 'trips' in data and data['trips']:
                    for trip in data['trips']:
                        if 'dates' in trip and trip['dates']:
                            for date in trip['dates']:
                                if date['dateOut'].startswith(flight['date']):
                                    flights = date.get('flights', [])
                                    if flights and 'regularFare' in flights[0]:
                                        price = float(flights[0]['regularFare']['fares'][0]['amount'])
                                        currency = data.get('currency', 'EUR')
                                        logging.info(f"Currency for {flight['description']}: {currency}")
                                        if currency.upper() == 'PLN':
                                            price = price * PLN_TO_EUR
                                            logging.info(f"Converted {flight['description']} price from PLN to EUR: €{price:.2f}")
                                        return f"€{price:.2f}"
                return "No price found"
            except requests.RequestException as e:
                logging.error(f"API error for {flight['description']} (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(delay)
                continue
        return "API error"
    except Exception as e:
        logging.error(f"Unexpected API error for {flight['description']}: {e}")
        return "API error"
    
    except Exception as e:
        logging.error(f"Unexpected API error for {flight['description']}: {e}")
        return "API error"

# Визуализация данных
def plot_prices():
    try:
        print("Starting to plot prices")
        df = pd.read_csv(CSV_FILE)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        for flight in FLIGHTS:
            flight_data = df[df['Flight'] == flight['description']]
            if not flight_data.empty:
                plt.figure(figsize=(10, 6))
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

# Отправка email с графиками
def send_email(prices, last_prices):
    try:
        print("Starting to send email")
        body = "Ryanair price changes:\n\n"
        send = False
        for price_info in prices:
            flight = price_info['flight']
            price = price_info['price']
            last_price = last_prices.get(flight, None)
            logging.info(f"Comparing prices for {flight}: current={price}, last={last_price}")
            if last_price and last_price != price and price not in ["No price found", "API error"]:
                body += f"{flight} on {price_info['date']}: {price} (was {last_price})\n"
                send = True
        if send:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_SENDER
            msg['To'] = EMAIL_RECEIVER
            msg['Subject'] = 'Ryanair Price Change Alert'
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

# Сбор цен и выполнение задач
def collect_prices():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Collecting prices at {timestamp}")
    logging.info(f"Collecting prices at {timestamp}")
    last_prices = {}
    try:
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
            last_prices = df.groupby('Flight').last()['Price'].to_dict()
            logging.info(f"Loaded last prices: {last_prices}")
            print(f"Loaded last prices: {last_prices}")
    except Exception as e:
        logging.error(f"Error loading last prices: {e}")
        print(f"Error loading last prices: {e}")
    prices = []
    for flight in FLIGHTS:
        price = get_flight_price_api(flight)
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, flight['description'], flight['date'], price])
        prices.append({
            'flight': flight['description'],
            'date': flight['date'],
            'price': price
        })
        logging.info(f"{flight['description']} on {flight['date']}: {price}")
        print(f"{flight['description']} on {flight['date']}: {price}")
        time.sleep(random.uniform(5, 10))
    plot_prices()
    send_email(prices, last_prices)
    logging.info("Price collection completed")
    print("Price collection completed")

def main():
    init_csv()
    collect_prices()

if __name__ == '__main__':
    main()