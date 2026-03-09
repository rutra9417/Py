from PIL import Image, ImageDraw, ImageFont
from telegram import Bot
import asyncio
from datetime import datetime, timedelta
import random
import os
import sys

# Базовая директория под Windows
base_dir = r"C:\Users\user\Documents\vip"

# Пути к файлам
img_path = os.path.join(base_dir, "main_oper.jpg")
tx_values_path = os.path.join(base_dir, "transaction_values.txt")
main_oper_path = os.path.join(base_dir, "main_oper.txt")
font_path = os.path.join(base_dir, "Roboto-Medium.ttf")
font_path_alt = os.path.join(base_dir, "roboto.regular.ttf")
output_path = os.path.join(base_dir, "outputScreenshot.png")

# Проверка наличия всех файлов
for file_path in [img_path, tx_values_path, main_oper_path]:
    if not os.path.isfile(file_path):
        print(f"❌ Файл не найден: {file_path}")
        sys.exit(1)

# Функция добавления текста с межбуквенным расстоянием
def add_text_to_image(image, text, coordinates, font_path, font_size, font_color, letter_spacing):
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()
    current_x, y = coordinates
    for char in text:
        draw.text((current_x, y), char, fill=font_color, font=font)
        try:
            bbox = font.getbbox(char)
            char_width = bbox[2] - bbox[0]
        except AttributeError:
            char_width, _ = font.getsize(char)  # для старых версий Pillow
        current_x += char_width + letter_spacing

# Загрузка изображения
img = Image.open(img_path)

# Параметры шрифта
font_size = 28
font_color = (255, 255, 255)
letter_spacing = 0

# Чтение файла транзакции
with open(tx_values_path, "r", encoding="utf-8") as file:
    lines = file.read().splitlines()

# Обработка даты и времени
date_time_str = lines[2]
formatted_datetime = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
adjusted_end_time = formatted_datetime - timedelta(minutes=2)
formatted_adjusted_end_time = adjusted_end_time.strftime("%#H:%M")  # Windows формат
formatted_date = formatted_datetime.strftime("%B %#d")
formatted_date1 = formatted_datetime.strftime("%#d %B %Y, %#H:%M")

# Случайные значения
number1 = random.randint(110000000, 119999999)
number2 = random.randint(37493000000, 37493999999)

# Добавление даты и времени
add_text_to_image(img, formatted_adjusted_end_time, (58, 27), font_path, 28, font_color, letter_spacing)
add_text_to_image(img, formatted_adjusted_end_time, (932, 1278), font_path, 25, font_color, letter_spacing)
add_text_to_image(img, formatted_adjusted_end_time, (869, 1454), font_path, 25, font_color, letter_spacing)
add_text_to_image(img, formatted_adjusted_end_time, (340, 1356), font_path, 25, font_color, letter_spacing)
add_text_to_image(img, formatted_date1, (829, 643), font_path, 18, (95, 100, 102), letter_spacing)
add_text_to_image(img, formatted_date, (458, 210), font_path, 27, font_color, letter_spacing)

# Получатель
recipient_input = lines[1]
formatted_recipient = recipient_input[:36]
add_text_to_image(img, formatted_recipient, (323, 1938), font_path, 32, (150, 192, 239), letter_spacing)

# Добавление текста из main_oper.txt
with open(main_oper_path, "r", encoding="utf-8") as file:
    text_lines = file.read().splitlines()

start_y = 1470
for line in text_lines:
    if line.startswith("Transaction:"):
        txid = line[-30:]
        add_text_to_image(img, line[:-56], (45, start_y), font_path_alt, 32, (246, 238, 238), letter_spacing)
        add_text_to_image(img, txid, (45, start_y + 38), font_path_alt, 32, (246, 238, 238), letter_spacing)
    else:
        add_text_to_image(img, line, (45, start_y), font_path_alt, 32, (246, 238, 238), letter_spacing)
    start_y += 38

# Рисуем случайные числа
try:
    font_small = ImageFont.truetype(font_path, 18)
except IOError:
    font_small = ImageFont.load_default()
draw = ImageDraw.Draw(img)
draw.text((950, 809), str(number1), fill=(71, 76, 78), font=font_small)
draw.text((930, 766), str(number2), fill=(71, 76, 78), font=font_small)
draw.text((930, 673), str(number2), fill=(71, 76, 78), font=font_small)

# Сохраняем результат
img.save(output_path)
print(f"✅ Изображение сохранено: {output_path}")

# Telegram бот
bot_token = "6143029111:AAE8_wMyTj7ZvIMWNr1TSQeEbCg2tpLiNDU"
bot = Bot(token=bot_token)

# Асинхронная отправка
async def send_image_to_users(chat_ids):
    try:
        for chat_id in chat_ids:
            with open(output_path, "rb") as image_file:
                await bot.send_photo(chat_id=chat_id, photo=image_file)
                print(f"✅ Отправлено: {chat_id}")
    except Exception as e:
        print("❌ Ошибка отправки:", e)

# Запуск
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        chat_ids = [740279851]  # Укажи нужные chat_id
        if chat_ids:
            loop.run_until_complete(send_image_to_users(chat_ids))
        else:
            print("⚠️ Список chat_ids пуст.")
    finally:
        loop.close()
