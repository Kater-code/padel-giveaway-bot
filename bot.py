"""Telegram giveaway bot with screenshot verification. See README."""
import asyncio
import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
GROUP_ID = int(os.environ["GROUP_ID"])
TZ = ZoneInfo(os.environ.get("TZ", "Europe/Kyiv"))
DATE_FMT = "%d.%m.%Y %H:%M"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
is_admin = F.from_user.id == ADMIN_ID


class NewGiveaway(StatesGroup):
    text = State()
    prize = State()
    draw_at = State()


# ---------- admin: create ----------

@dp.message(CommandStart(), F.chat.type == "private")
async def start(m: Message):
    await m.answer("Привет! Нажми «Участвовать» под постом розыгрыша, потом пришли сюда скрин подписки.")


@dp.message(Command("new"), is_admin, F.chat.type == "private")
async def new_giveaway(m: Message, state: FSMContext):
    await state.set_state(NewGiveaway.text)
    await m.answer("Текст поста:")


@dp.message(NewGiveaway.text, is_admin)
async def new_text(m: Message, state: FSMContext):
    await state.update_data(text=m.text)
    await state.set_state(NewGiveaway.prize)
    await m.answer("Приз (одной строкой):")


@dp.message(NewGiveaway.prize, is_admin)
async def new_prize(m: Message, state: FSMContext):
    await state.update_data(prize=m.text)
    await state.set_state(NewGiveaway.draw_at)
    await m.answer(f"Дата итогов в формате {DATE_FMT.replace('%', '')} (например 25.09.2026 20:00):")


@dp.message(NewGiveaway.draw_at, is_admin)
async def new_draw_at(m: Message, state: FSMContext):
    try:
        draw_at = datetime.strptime(m.text.strip(), DATE_FMT).replace(tzinfo=TZ).astimezone(timezone.utc)
    except ValueError:
        await m.answer("Не понял дату, попробуй ещё раз: 25.09.2026 20:00")
        return
    data = await state.get_data()
    await state.clear()
    gid = db.create_giveaway(GROUP_ID, data["text"], data["prize"], draw_at)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎾 Участвовать", callback_data=f"join:{gid}")]])
    post = await bot.send_message(GROUP_ID, data["text"], reply_markup=kb)
    db.set_message_id(gid, post.message_id)
    await m.answer(f"Опубликовано. Розыгрыш #{gid}, итоги {m.text.strip()}.")


# ---------- participants ----------

@dp.callback_query(F.data.startswith("join:"))
async def join(cq: CallbackQuery):
    gid = int(cq.data.split(":")[1])
    db.add_participant(gid, cq.from_user.id, cq.from_user.username or cq.from_user.full_name)
    me = (await bot.me()).username
    await cq.answer(f"Ты в игре! Теперь пришли скрин подписки боту @{me} в личку.", show_alert=True)


@dp.message(F.photo, F.chat.type == "private")
async def screenshot(m: Message):
    gid = db.set_screenshot(m.from_user.id, m.photo[-1].file_id)
    if gid is None:
        await m.answer("Сначала нажми «Участвовать» под постом розыгрыша.")
    else:
        await m.answer("Скрин принят, ты участвуешь ✅")


# ---------- admin: review & draw ----------

def _gid(m: Message) -> int | None:
    parts = m.text.split()
    if len(parts) > 1 and parts[1].isdigit():
        return int(parts[1])
    latest = db.latest_giveaway()
    return latest["id"] if latest else None


@dp.message(Command("participants"), is_admin, F.chat.type == "private")
async def participants(m: Message):
    gid = _gid(m)
    if gid is None:
        return await m.answer("Розыгрышей нет.")
    people = db.participants(gid)
    verified = [p for p in people if p["screenshot_file_id"]]
    await m.answer(f"Розыгрыш #{gid}: {len(people)} нажали, {len(verified)} со скрином.")
    for p in verified:
        await bot.send_photo(m.chat.id, p["screenshot_file_id"], caption=f"@{p['username']} ({p['user_id']})")


@dp.message(Command("redraw"), is_admin, F.chat.type == "private")
async def redraw(m: Message):
    gid = _gid(m)
    if gid is None:
        return await m.answer("Розыгрышей нет.")
    await announce(db.get_giveaway(gid), db.redraw(gid))
    await m.answer("Переразыграно.")


async def announce(g: dict, winner: dict | None):
    text = (f"🏆 Победитель: @{winner['username']}! Приз — {g['prize']}. Напишем тебе в личку."
            if winner else "Розыгрыш завершён: никто не прислал скрин подписки 😔")
    await bot.send_message(g["chat_id"], text, reply_to_message_id=g["message_id"])


async def draw_loop():
    while True:
        for g in db.due_giveaways(datetime.now(timezone.utc)):
            try:
                await announce(g, db.pick_winner(g["id"]))
            except Exception:
                logging.exception("draw failed for giveaway %s", g["id"])
        await asyncio.sleep(60)


async def main():
    logging.basicConfig(level=logging.INFO)
    db.init()
    asyncio.create_task(draw_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
