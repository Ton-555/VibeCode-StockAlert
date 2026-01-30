import yfinance as yf
import pandas as pd
import requests
import json
import os

# --- 1. ตั้งค่า ---
# ใส่รายชื่อหุ้นที่ต้องการ (Ticker Symbol)แส
STOCK_LIST = ['AAPL', 'TSLA', 'MSFT', 'NVDA', 'GOOGL']

# URL จากขั้นตอนที่ 1 (ถ้าทดสอบในคอมให้ใส่ตรงนี้ แต่ถ้าขึ้น GitHub ให้ใช้วิธี Environment Variable)
# เพื่อความปลอดภัย เบื้องต้นคุณใส่ URL ตรงนี้เพื่อเทสก่อนได้เลย
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1466711413979353152/N_ci6sZ5hvBP--yJ8a8BHKWNSDu2Ew2dcehfiMqVV8qDaKWRLKHrTI39U3FTbxR2Y09x" 

def analyze_stock(symbol):
    try:
        # ดึงข้อมูลย้อนหลัง 3 เดือน
        data = yf.download(symbol, period="3mo", interval="1d", progress=False)
        if len(data) < 50: return None

        # ราคาปัจจุบัน
        current_price = float(data['Close'].iloc[-1].iloc[0] if isinstance(data['Close'], pd.DataFrame) else data['Close'].iloc[-1])
        
        # คำนวณ SMA 50 (เส้นค่าเฉลี่ย)
        sma_50 = data['Close'].rolling(window=50).mean().iloc[-1]
        if isinstance(sma_50, pd.Series): sma_50 = float(sma_50.iloc[0])
        else: sma_50 = float(sma_50)

        # แนวรับ-แนวต้าน (High/Low 20 วัน)
        resistance = float(data['High'].tail(20).max().iloc[0] if isinstance(data['High'], pd.DataFrame) else data['High'].tail(20).max())
        support = float(data['Low'].tail(20).min().iloc[0] if isinstance(data['Low'], pd.DataFrame) else data['Low'].tail(20).min())

        # ตัดสินแนวโน้ม
        trend_icon = "🟢" if current_price > sma_50 else "🔴"
        trend_text = "ขาขึ้น (Bullish)" if current_price > sma_50 else "ขาลง (Bearish)"

        return {
            "symbol": symbol,
            "price": current_price,
            "trend": f"{trend_icon} {trend_text}",
            "support": support,
            "resistance": resistance
        }
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

def send_discord_message(results):
    # สร้างข้อความแบบ Embed (กล่องสวยๆ)
    embeds = []
    
    for item in results:
        color = 5763719 if "ขาขึ้น" in item['trend'] else 15548997 # เขียว หรือ แดง
        
        embed = {
            "title": f"🇺🇸 {item['symbol']} : ${item['price']:.2f}",
            "color": color,
            "fields": [
                {"name": "Trend", "value": item['trend'], "inline": True},
                {"name": "Support", "value": f"${item['support']:.2f}", "inline": True},
                {"name": "Resistance", "value": f"${item['resistance']:.2f}", "inline": True}
            ]
        }
        embeds.append(embed)

    # Payload สำหรับส่งไป Discord
    payload = {
        "username": "Stock Assistant",
        "content": "**📊 รายงานหุ้น US ประจำวัน** (Timeframe: Day)",
        "embeds": embeds
    }

    # ส่งข้อมูล
    response = requests.post(
        DISCORD_WEBHOOK_URL, 
        data=json.dumps(payload), 
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 204:
        print("✅ ส่งเข้า Discord สำเร็จ!")
    else:
        print(f"❌ ส่งไม่ผ่าน: {response.status_code} {response.text}")

# --- รันโปรแกรม ---
if __name__ == "__main__":
    results = []
    print("⏳ กำลังวิเคราะห์ข้อมูล...")
    for stock in STOCK_LIST:
        res = analyze_stock(stock)
        if res:
            results.append(res)
    
    if results:
        send_discord_message(results)
    else:
        print("ไม่พบข้อมูลหุ้น")