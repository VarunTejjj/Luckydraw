import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
import qrcode
from PIL import Image, ImageDraw, ImageFont
import logging

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Railway Environment Variables
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

UPIS = [x.strip() for x in os.getenv('UPIS', 'varunloves@fam').split(',')]
ADMINS = [x.strip() for x in os.getenv('ADMINS', 'VarunsLuckyDraw,8935742943').split(',')]

# Persistent storage
DATA_DIR = '/data'
os.makedirs(DATA_DIR, exist_ok=True)

# Session
SESSION_NAME = 'lucky_draw_session'
PARTICIPANTS_FILE = os.path.join(DATA_DIR, 'participants.json')

client = TelegramClient(SESSION_NAME, api_id, api_hash)

# Initialize file
if not os.path.exists(PARTICIPANTS_FILE):
    with open(PARTICIPANTS_FILE, 'w') as f:
        json.dump([], f)

user_states = {}

async def load_participants():
    try:
        with open(PARTICIPANTS_FILE, 'r') as f:
            return json.load(f)
    except:
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
    except:
        font = ImageFont.load_default()
    
    texts = ["Lucky Draw Participation", f"User ID: {user_id}", f"Time: {timestamp}", f"Amount: ₹{amount}"]
    
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
        chat_id = event.chat_id
        message_text = event.raw_text.strip().lower()

        if user_id not in user_states:
            user_states[user_id] = 'waiting_yes_no'
            await event.reply("Kya Apko Lucky Draw Meh Join Hona Hei?\n\nYes or No bhej do")
            return

        state = user_states.get(user_id)

        if state == 'waiting_yes_no':
            if message_text == "yes":
                user_states[user_id] = 'waiting_payment'
                await event.reply("T&C\nThe account you get it will depend on your luck \nWinner gets ₹10 in return")
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                qr_file = generate_qr(UPIS[0], "5", str(user_id), now)
                await event.reply(file=qr_file, message=f"Lucky Draw Participation\nUser ID: {user_id}\nTime: {now}\n\nScreenshot bhejo")
            elif message_text == "no":
                user_states[user_id] = 'normal'
                await event.reply('Lucky Draw Join likh ke join kar sakte ho baad me')

        elif state == 'waiting_payment':
            if "new qr" in message_text:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                qr_file = generate_qr(UPIS[0], "5", str(user_id), now)
                await event.reply(file=qr_file, message="New QR")
            elif event.message.photo or "screenshot" in message_text:
                await event.reply("Wait for admin approval ✅")
                user_states[user_id] = 'waiting_approval'
            else:
                await event.reply("Screenshot bhejo ya NEW QR likho")

        elif state == 'waiting_approval':
            await event.reply("Admin approval ka intezar hai")

    except Exception as e:
        logger.error(f"Error: {e}")

@client.on(events.NewMessage(pattern=r'/approved', func=lambda e: e.is_private))
async def handle_approval(event):
    try:
        if str(event.sender_id) not in ADMINS:
            return
        chat_id = event.chat_id
        await event.reply("You Have Successfully Participated 👍🏻\nGood Luck 😸")
        data = {"chat_id": chat_id, "time": datetime.now().isoformat(), "status": "Approved"}
        await save_participant(data)
        try:
            await client.delete_dialog(chat_id, revoke=True)
        except:
            pass
    except Exception as e:
        logger.error(f"Approval error: {e}")

async def main():
    await client.start()
    logger.info("✅ Lucky Draw Bot Started on Railway!")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
