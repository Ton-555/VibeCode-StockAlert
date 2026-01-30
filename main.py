import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# --- ส่วนเช็คระบบ (Print Check) ---
print("!!! SYSTEM CHECK: Code is initialized !!!")

# โหลดค่าจากไฟล์ .env
load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
STOCK_LIST = ["AAPL", "TSLA", "GOOGL", "MSFT", "NVDA"]

# เช็ค URL
if not DISCORD_WEBHOOK_URL:
    # เตือนแต่ไม่ให้โปรแกรมพัง (เผื่อรันใน GitHub Actions แล้วส่ง Secret มาทาง env)
    print("⚠️ Warning: DISCORD_WEBHOOK_URL not found in .env (Check GitHub Secrets)")

def get_scalar(val):
    """ฟังก์ชันช่วยแปลงค่าให้เป็น float ธรรมดา"""
    if isinstance(val, (pd.Series, pd.DataFrame)):
        val = val.values.flatten()[0]
    return float(val)

def get_stock_logo(symbol):
    """ฟังก์ชันดึง URL โลโก้ของหุ้น"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if 'logo_url' in info and info['logo_url']:
            return info['logo_url']
        if 'website' in info and info['website']:
            website = info['website'].replace("https://", "").replace("http://", "").replace("www.", "")
            domain = website.split('/')[0]
            return f"https://logo.clearbit.com/{domain}"
    except Exception:
        pass
    return ""

def analyze_stock(symbol):
    try:
        # ดึงข้อมูล (เอา multi=False ออกเพื่อให้รองรับทุกเวอร์ชัน)
        data = yf.download(symbol, period="3mo", interval="1d", progress=False)
        
        if len(data) < 50: return None

        # --- คำนวณค่าต่างๆ ---
        current_close = data['Close'].iloc[-1]
        current_price = get_scalar(current_close)
        
        # คำนวณ % Change
        prev_close = get_scalar(data['Close'].iloc[-2])
        price_change = current_price - prev_close
        percent_change = (price_change / prev_close) * 100
        percent_str = f"{percent_change:+.2f}%"
        
        # SMA 50
        sma_50 = get_scalar(data['Close'].rolling(window=50).mean().iloc[-1])

        # Pivot Points
        prev_candle = data.iloc[-2] 
        prev_high = get_scalar(prev_candle['High'])
        prev_low = get_scalar(prev_candle['Low'])
        prev_close_pivot = get_scalar(prev_candle['Close'])

        pivot = (prev_high + prev_low + prev_close_pivot) / 3
        
        r1 = (2 * pivot) - prev_low
        r2 = pivot + (prev_high - prev_low)
        r3 = prev_high + 2 * (pivot - prev_low)

        s1 = (2 * pivot) - prev_high
        s2 = pivot - (prev_high - prev_low)
        s3 = prev_low - 2 * (prev_high - pivot)

        trend_icon = "🟢" if current_price > sma_50 else "🔴"
        trend_text = "Bullish" if current_price > sma_50 else "Bearish"

        logo_url = get_stock_logo(symbol)

        return {
            "symbol": symbol,
            "price": current_price,
            "change_str": percent_str,
            "logo_url": logo_url,
            "trend": f"{trend_icon} {trend_text}",
            "supports": [s1, s2, s3],
            "resistances": [r1, r2, r3]
        }

    except Exception as e:
        print(f"⚠️ Error analyzing {symbol}: {e}")
        return None

def send_discord_message(results):
    embeds = []
    report_date = datetime.now().strftime("%d %b %Y")

    for item in results:
        color = 5763719 if "Bullish" in item['trend'] else 15548997
        change_icon = "📈" if "+" in item['change_str'] else "📉"
        
        res_str = f"R3: {item['resistances'][2]:.2f}\nR2: {item['resistances'][1]:.2f}\nR1: {item['resistances'][0]:.2f}"
        sup_str = f"S1: {item['supports'][0]:.2f}\nS2: {item['supports'][1]:.2f}\nS3: {item['supports'][2]:.2f}"

        embed = {
            "title": f"🇺🇸 {item['symbol']} : ${item['price']:.2f} ({change_icon} {item['change_str']})",
            "description": f"Trend: **{item['trend']}**",
            "color": color,
            "fields": [
                {"name": "📉 Support", "value": f"```\n{sup_str}\n```", "inline": True},
                {"name": "📈 Resistance", "value": f"```\n{res_str}\n```", "inline": True}
            ]
        }
        if item['logo_url']:
            embed["thumbnail"] = {"url": item['logo_url']}

        embeds.append(embed)

    payload = {
        "username": "Stock Assistant",
        "content": f"**📊 รายงานหุ้น US** 📅 {report_date}",
        "embeds": embeds
    }

    print("🚀 กำลังส่ง HTTP Request ไปยัง Discord...")
    
    # --- ส่วนที่เติมให้ครบ (Request) ---
    try:
        if not DISCORD_WEBHOOK_URL:
            print("❌ ยกเลิกการส่ง: ไม่พบ URL")
            return

        response = requests.post(
            DISCORD_WEBHOOK_URL, 
            data=json.dumps(payload), 
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 204:
            print("✅ ส่งเข้า Discord สำเร็จ!")
        else:
            print(f"❌ ส่งไม่ผ่าน: {response.status_code} {response.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

# ==========================================
# 👇 ส่วนที่สำคัญที่สุด (Main Execution Block)
# ==========================================
if __name__ == "__main__":
    print("⏳ Start Process: กําลังเริ่มวิเคราะห์หุ้น...") 
    
    results = []
    for stock in STOCK_LIST:
        print(f"   🔎 Checking {stock}...")
        res = analyze_stock(stock)
        if res:
            results.append(res)
    
    if results:
        print(f"📊 ได้ข้อมูลครบ {len(results)} ตัว.. กำลังส่งข้อมูล")
        send_discord_message(results)
    else:
        print("⚠️ ไม่พบข้อมูลหุ้นเลย (ตรวจสอบเน็ต หรือ ชื่อหุ้น)")