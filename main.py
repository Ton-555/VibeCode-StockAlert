import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# รายชื่อหุ้นที่ต้องการตรวจสอบ (ต้องระบุตรงนี้)
STOCK_LIST = ["AAPL", "TSLA", "GOOGL", "MSFT", "NVDA"]

if not DISCORD_WEBHOOK_URL:
    raise ValueError("ไม่พบ DISCORD_WEBHOOK_URL กรุณาตั้งค่า Environment Variable")

def get_scalar(val):
    """ฟังก์ชันช่วยแปลงค่าให้เป็น float ธรรมดา ป้องกันปัญหาจาก pandas series"""
    if isinstance(val, (pd.Series, pd.DataFrame)):
        return float(val.iloc[0])
    return float(val)

def analyze_stock(symbol):
    try:
        # ดึงข้อมูลย้อนหลัง (ใช้ 3 เดือนเหมือนเดิมเพื่อให้มีข้อมูลพอทำ SMA)
        data = yf.download(symbol, period="3mo", interval="1d", progress=False)
        
        # ตรวจสอบว่ามีข้อมูลเพียงพอหรือไม่
        if len(data) < 50: return None

        # --- ส่วนที่ 1: ราคาและ SMA ---
        # ราคาปัจจุบัน (แท่งล่าสุด)
        current_close = data['Close'].iloc[-1]
        current_price = get_scalar(current_close)

        # SMA 50
        sma_50_series = data['Close'].rolling(window=50).mean()
        sma_50 = get_scalar(sma_50_series.iloc[-1])

        # --- ส่วนที่ 2: คำนวณ Pivot Points (แนวรับ-ต้าน 3 ระดับ) ---
        # ใช้ข้อมูลของ "เมื่อวาน" (แท่งก่อนหน้า -2) เพื่อคำนวณกรอบของ "วันนี้"
        # เพราะถ้ารันระหว่างวัน แท่งล่าสุด (-1) อาจยังไม่จบวัน
        prev_candle = data.iloc[-2] 
        
        prev_high = get_scalar(prev_candle['High'])
        prev_low = get_scalar(prev_candle['Low'])
        prev_close = get_scalar(prev_candle['Close'])

        # สูตร Standard Pivot Points
        pivot = (prev_high + prev_low + prev_close) / 3
        
        # แนวต้าน (Resistance) 3 ระดับ
        r1 = (2 * pivot) - prev_low
        r2 = pivot + (prev_high - prev_low)
        r3 = prev_high + 2 * (pivot - prev_low)

        # แนวรับ (Support) 3 ระดับ
        s1 = (2 * pivot) - prev_high
        s2 = pivot - (prev_high - prev_low)
        s3 = prev_low - 2 * (prev_high - pivot)

        # --- ส่วนที่ 3: สรุปผล ---
        trend_icon = "🟢" if current_price > sma_50 else "🔴"
        trend_text = "Bullish (เหนือ SMA50)" if current_price > sma_50 else "Bearish (ใต้ SMA50)"

        return {
            "symbol": symbol,
            "price": current_price,
            "trend": f"{trend_icon} {trend_text}",
            "supports": [s1, s2, s3],    # ส่งเป็น List
            "resistances": [r1, r2, r3]  # ส่งเป็น List
        }

    except Exception as e:
        print(f"⚠️ Error analyzing {symbol}: {e}")
        return None

def send_discord_message(results):
    embeds = []
    
    # หาวันที่ปัจจุบัน และจัดรูปแบบ (เช่น 30 Jan 2026)
    report_date = datetime.now().strftime("%d %b %Y")

    for item in results:
        # กำหนดสีขอบ (เขียว/แดง)
        color = 5763719 if "Bullish" in item['trend'] else 15548997
        
        # จัด Format ข้อความแนวรับแนวต้านให้อยู่ในบรรทัดเดียว หรือแยกบรรทัดให้อ่านง่าย
        res_str = f"R3: {item['resistances'][2]:.2f}\nR2: {item['resistances'][1]:.2f}\nR1: {item['resistances'][0]:.2f}"
        sup_str = f"S1: {item['supports'][0]:.2f}\nS2: {item['supports'][1]:.2f}\nS3: {item['supports'][2]:.2f}"

        embed = {
            "title": f"🇺🇸 {item['symbol']} : ${item['price']:.2f}",
            "description": f"Trend: **{item['trend']}**",
            "color": color,
            "fields": [
                {"name": "📉 Support Levels", "value": f"```\n{sup_str}\n```", "inline": True},
                {"name": "📈 Resistance Levels", "value": f"```\n{res_str}\n```", "inline": True}
            ],
            "footer": {
                "text": "Analysis by Python Bot"
            }
        }
        embeds.append(embed)

    # Payload หลัก
    payload = {
        "username": "Stock Assistant",
        # เพิ่มวันที่ตรงนี้
        "content": f"**📊 รายงานหุ้น US ประจำวัน**\n📅 ประจำวันที่: **{report_date}** (Timeframe: Day)",
        "embeds": embeds
    }

    try:
        # ส่วนที่พยายามส่งข้อมูล
        response = requests.post(
            DISCORD_WEBHOOK_URL, 
            data=json.dumps(payload), 
            headers={"Content-Type": "application/json"}
        )
        
        # เช็คว่า Server ตอบกลับมาว่าสำเร็จหรือไม่ (204 = No Content คือสำเร็จสำหรับ Discord)
        if response.status_code == 204:
            print("✅ ส่งเข้า Discord สำเร็จ!")
        else:
            # กรณีส่งไปได้ แต่ Discord ปฏิเสธ (เช่น ลิงก์ผิด, format ผิด)
            print(f"❌ ส่งไม่ผ่าน: {response.status_code} {response.text}")

    except Exception as e:
        # ส่วนนี้จะทำงานก็ต่อเมื่อ "โปรแกรมพัง" ก่อนที่จะได้คำตอบ 
        # เช่น เน็ตหลุด, หา URL ไม่เจอ, หรือ Library requests มีปัญหา
        print(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")