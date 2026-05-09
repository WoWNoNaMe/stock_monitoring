import os
import requests
from datetime import datetime

TELEGRAM_TOKEN = "8698021994:AAH42XQB9BvjrzFBHooQ2fDB1CYmczPuzpg"
GROQ_API_KEY = "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"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_telegram(chat_id, message):
    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    })

def get_stock_research(company_name):
    today = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""Ma van {today}. A felhasználó ezt a részvényt / céget kérdezte: "{company_name}"

Írj egy részletes összefoglalót a következő struktúrában:

1. 📉 MAI MOZGÁS ÉS OKA
- Mi történt ma a részvénnyel?
- Mi okozta az esetleges esést vagy emelkedést?
- Volt-e fontos hír, bejelentés, makrogazdasági esemény?

2. 🏢 A CÉG AKTUÁLIS HELYZETE
- Mi újság a céggel az elmúlt hetekben?
- Legutóbbi earnings, termék bejelentések, szerződések?
- Van-e valami fontos fejlemény?

3. 🔮 KILÁTÁSOK ÉS ELEMZŐI VÉLEMÉNYEK
- Mit mondanak az elemzők?
- Mi a piaci hangulat a részvény körül?
- Milyen kockázatok és lehetőségek vannak?

4. 📰 LEGFRISSEBB HÍREK
- 3-5 legfontosabb friss hír röviden

Legyél konkrét, tömör és hasznos. Magyar nyelven válaszolj."""

    response = requests.post(GROQ_URL, 
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,
            "temperature": 0.7
        }
    )
    
    data = response.json()
    return data["choices"][0]["message"]["content"]

def process_updates(offset=None):
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    
    response = requests.get(f"{TELEGRAM_URL}/getUpdates", params=params)
    return response.json()

def main():
    print("Stock Research Bot elindult!")
    offset = None
    
    while True:
        try:
            updates = process_updates(offset)
            
            if not updates.get("ok"):
                continue
                
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                
                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "").strip()
                
                if not text or not chat_id:
                    continue
                
                if text.startswith("/start"):
                    send_telegram(chat_id, 
                        "👋 Üdvözöllek!\n\nÍrj be egy részvény nevét vagy ticker szimbólumát és összefoglalót küldök róla.\n\nPéldák:\n• palantir\n• NVDA\n• tesla\n• microsoft")
                    continue
                
                print(f"Kérdés: {text}")
                send_telegram(chat_id, f"🔍 Keresem a <b>{text}</b> információit, egy pillanat...")
                
                result = get_stock_research(text)
                send_telegram(chat_id, result)
                print(f"Válasz elküldve: {text}")
                
        except Exception as e:
            print(f"Hiba: {e}")

if __name__ == "__main__":
    main()
