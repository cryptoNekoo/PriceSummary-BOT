import logging
import time
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InputFile
from collections import Counter
import requests
from config import BOT_TOKEN, TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO)

url = "https://api.lzt.market/bulk-items"
headers = {"accept": "application/json", "authorization": f"Bearer {TOKEN}"}

async def process_ids(item_ids):
    def chunk_list(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    id_count = Counter(item_ids)
    unique_ids = [id for id, count in id_count.items() if count == 1]
    duplicates = [id for id, count in id_count.items() if count > 1]
    item_id_chunks = list(chunk_list(unique_ids, 250))

    responses = []
    for index, chunk in enumerate(item_id_chunks):
        data = {"item_id[]": chunk}
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            responses.append(response.json())
        else:
            logging.info(f"Request Error for chunk: HTTP {response.status_code}")
        time.sleep(3)

    sold_accounts = []
    unsold_accounts = []
    total_sold = 0
    total_unsold = 0
    errors = []

    for response in responses:
        items = response.get('items', {})
        for item_id, details in items.items():
            if isinstance(details, dict):
                item_details = details.get("item", {})
                item_state = item_details.get("item_state", "Unknown")
                price = item_details.get("priceWithSellerFee", "Unknown")
                link = f"https://lzt.market/{item_id}/"
                if item_state == "paid":
                    sold_accounts.append((link, price))
                    total_sold += price
                elif item_state == "deleted":
                    errors.append(link)
                else:
                    unsold_accounts.append((link, price))
                    total_unsold += price
            else:
                errors.append(item_id)

    with open("result.txt", "w", encoding='utf-8') as file:
        file.write(f"📊Проданных аккаунтов: {len(sold_accounts)}\n")
        file.write(f"🔒Не проданных аккаунтов: {len(unsold_accounts)}\n\n")
        file.write(f"💰 Общая сумма всех проданных аккаунтов: {total_sold} рублей (-30%: {int(total_sold * 0.7)})\n")
        for link, price in sold_accounts:
            file.write(f"- {link} - {price}\n")
        file.write("\n🛡️Не проданные аккаунты:\n")
        for link, price in unsold_accounts:
            file.write(f"- {link} - {price}\n")
        file.write(f"\n💵Общая сумма не проданных аккаунтов на данный момент: {total_unsold} рублей (-30%: {int(total_unsold * 0.7)})\n")
        file.write("\n🔍Найденные дубли:\n")
        if duplicates:
            for dup in duplicates:
                file.write(f"❌https://lzt.market/{dup}\n")
        else:
            file.write("❌Нету\n")
        if errors:
            file.write("\n🗑️ *Удаленные/нет доступа:*\n")
            for error in errors:
                file.write(f"- {error}\n")

    return "result.txt"

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Отправь мне ссылки текстом — максимум 130 ссылок в одном сообщении.\nЕсли у тебя больше ссылок, лучше отправь их файлом.")

@dp.message_handler(content_types=['document'])
async def handle_docs(message: types.Message):
    document_id = message.document.file_id
    file_info = await bot.get_file(document_id)
    file_path = file_info.file_path
    file = await bot.download_file(file_path)
    
    ids = []
    with open("temp_file.txt", "wb") as f:
        f.write(file.read())
    with open("temp_file.txt", "r") as f:
        lines = f.readlines()
        ids = [int(line.strip().split('/')[-2]) for line in lines]

    result_file = await process_ids(ids)
    await message.reply_document(InputFile(result_file))

@dp.message_handler()
async def handle_text(message: types.Message):
    await message.reply("Обработка данных начата. Пожалуйста, подождите...")
    chat_id = message.chat.id
    message_id = message.message_id
    ids = [int(line.strip().split('/')[-2]) for line in message.text.splitlines()]
    result_file = await process_ids(ids)
    await bot.send_document(chat_id, document=InputFile(result_file))
    await bot.delete_message(chat_id, message_id)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
