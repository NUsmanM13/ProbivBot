import asyncio
import logging
import aiohttp # Asinxron HTTP so'rovlari uchun yangi kutubxona

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode

# --- Sozlamalar ---
# @BotFather dan olgan bot tokeningizni shu yerga qo'ying
BOT_TOKEN = "7713895772:AAET7IEQNyxOxSuFmXuYH3yvpiV0x27Wkfk"

# Siz taqdim etgan API uchun ma'lumotlar
API_URL = "https://api-dyxless.cfd/query"
API_TOKEN = "493820ea-56be-4c4a-816e-a87294981fb5"


# --- Haqiqiy API bilan ishlash funksiyasi ---
async def get_data_from_real_api(query: str) -> tuple:
    """
    Haqiqiy API ga POST so'rovini yuboradi va natijani qaytaradi.
    Natija (status, ma'lumot) ko'rinishidagi kortej (tuple) bo'ladi.
    """
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        "query": query,
        "token": API_TOKEN
    }

    try:
        # aiohttp sessiyasi bilan asinxron so'rov yuborish
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, headers=headers, json=payload, timeout=30) as response:
                # HTTP status kodini tekshirish
                if response.status == 200:
                    data = await response.json()
                    # API ba'zan muvaffaqiyatli (200) bo'lsa ham, "topilmadi" degan javob berishi mumkin
                    if data.get("data") is None or not data.get("data"):
                         return ("NOT_FOUND", f"`{query}` uchun ma'lumot topilmadi.")
                    return ("SUCCESS", data.get("data"))
                else:
                    # Agar server xatolik statusi qaytarsa (4xx, 5xx)
                    error_details = await response.text()
                    return ("API_ERROR", f"Status kodi: {response.status}\nXatolik: {error_details}")

    except aiohttp.ClientConnectorError as e:
        # Ulanish xatoliklarini ushlash (masalan, DNS topilmadi, ulanish rad etildi)
        logging.error(f"Ulanish xatoligi: {e}")
        return ("CONNECTION_ERROR", "API serveriga ulanib bo'lmadi. Server manzilini tekshiring yoki internet aloqangizni nazorat qiling.")
    except asyncio.TimeoutError:
        # So'rov uchun ajratilgan vaqt tugaganda yuz beradigan xatolik
        logging.error("API so'rovi uchun vaqt tugadi.")
        return ("CONNECTION_ERROR", "API serveridan javob olish uchun ajratilgan vaqt tugadi. Server yuklangan bo'lishi mumkin.")
    except Exception as e:
        # Boshqa kutilmagan xatoliklarni ushlash
        logging.error(f"Kutilmagan xatolik: {e}")
        return ("UNKNOWN_ERROR", f"Noma'lum xatolik yuz berdi: {e}")


# --- Bot logikasi ---

# Foydalanuvchi holatlarini boshqarish uchun
class UserQueryState(StatesGroup):
    waiting_for_query = State()

# Dispatcher obyekti
dp = Dispatcher()

# /start buyrug'iga javob beruvchi handler
@dp.message(CommandStart())
async def send_welcome(message: types.Message, state: FSMContext):
    """Foydalanuvchi botni ishga tushirganda chaqiriladi."""
    await state.clear()
    user_full_name = message.from_user.full_name
    await message.answer(
        f"Assalomu alaykum, {user_full_name}! 👋\n\n"
        "Men telefon raqami yoki username orqali ma'lumot qidiruvchi botman.\n\n"
        "<b>Qidirish uchun telefon raqami yoki username kiriting:</b>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(UserQueryState.waiting_for_query)

# Foydalanuvchi so'rovini qabul qilib, uni qayta ishlovchi handler
@dp.message(UserQueryState.waiting_for_query)
async def process_query(message: types.Message, state: FSMContext):
    """Foydalanuvchi qidiruv so'rovini kiritganda ishlaydi."""
    if not message.text or "/" in message.text:
        await message.answer("Iltimos, buyruq emas, qidiruv uchun ma'lumot (telefon raqam/username) kiriting.")
        return

    query = message.text.strip()
    loading_message = await message.answer(f"⏳ <code>{query}</code> bo'yicha ma'lumotlar qidirilmoqda...")

    # Haqiqiy APIga so'rov yuborish
    status, result = await get_data_from_real_api(query)

    # Natijani tahlil qilib, foydalanuvchiga javob yuborish
    if status == "SUCCESS":
        # API dan kelgan ma'lumotlarni chiroyli formatda yig'amiz
        # API javobi bir nechta obyektlardan iborat ro'yxat bo'lishi mumkin
        response_text = f"✅ <b>Natijalar: <code>{query}</code></b>\n\n"
        
        if isinstance(result, list):
            for i, item in enumerate(result, 1):
                name = item.get('name', 'Noma\'lum')
                phone = item.get('phone', 'Noma\'lum')
                telegram_id = item.get('telegram_id', 'Noma\'lum')
                username = f"@{item['username']}" if item.get('username') else 'Mavjud emas'
                
                response_text += (
                    f"📄 <b>Natija #{i}</b>\n"
                    f"  👤 <b>Ism:</b> {name}\n"
                    f"  📞 <b>Telefon:</b> <code>{phone}</code>\n"
                    f"  🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
                    f"  🌐 <b>Username:</b> {username}\n"
                    "--------------------\n"
                )
        else: # Agar bitta obyekt kelsa
             response_text = "Natija formati noma'lum."

        await loading_message.edit_text(response_text, parse_mode=ParseMode.HTML)

    elif status == "NOT_FOUND":
        await loading_message.edit_text(f"❌ {result}", parse_mode=ParseMode.HTML)

    else: # Barcha turdagi xatoliklar uchun
        error_title = {
            "API_ERROR": "API Xatoligi",
            "CONNECTION_ERROR": "Ulanishda Xatolik",
            "UNKNOWN_ERROR": "Noma'lum Xatolik"
        }.get(status, "Xatolik")

        error_message = (
            f"❗️<b>{error_title}</b>\n\n"
            f"So'rovni bajarishda muammo yuzaga keldi.\n\n"
            f"<i>Texnik ma'lumot:</i>\n<code>{result}</code>"
        )
        await loading_message.edit_text(error_message, parse_mode=ParseMode.HTML)

    await message.answer("Yana boshqa ma'lumot qidirasizmi? Marhamat, kiriting.")
    await state.set_state(UserQueryState.waiting_for_query)

# Botni ishga tushuruvchi asosiy funksiya
async def main() -> None:
    bot = Bot(BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())