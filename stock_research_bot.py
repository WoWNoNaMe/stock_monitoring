import os
import requests
from datetime import datetime, timedelta
 
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
 
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
 
def send_telegram(chat_id, message):
    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    })
 
def search_news(query):
    today = datetime.now()
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": week_ago,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 5,
        "apiKey": NEWS_API_KEY
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    articles = data.get("articles", [])
    news_text = ""
    news_links = []
    
    for i, article in enumerate(articles):
        title = article.get("title", "")
        description = article.get("description", "")
        url = article.get("url", "")
        published = article.get("publishedAt", "")[:10]
        source = article.get("source", {}).get("name", "")
        
        news_text += f"\n[{i+1}] {title}\n{description}\nForrás: {source} ({published})\n"
        news_links.append(f"{i+1}. <a href='{url}'>{title[:60]}...</a> – {source}")
    
    return news_text, news_links
 
def get_stock_research(company_name, news_text):
    today = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""Ma van {today}. A felhasználó ezt kérdezte: "{company_name}"
 
Az alábbi friss hírek állnak rendelkezésre az elmúlt 7 napból:
{news_text}
 
Ezek alapján írj egy tömör, hasznos összefoglalót a következő struktúrában:
 
📉 MAI/KÖZELMÚLTI MOZGÁS
Mi történt? Mi okozta az esést vagy emelkedést?
 
🏢 AKTUÁLIS HELYZET
Mi újság a céggel? Fontos bejelentések, earnings, szerződések?
 
🔮 KILÁTÁSOK
Elemzői vélemények, kockázatok, lehetőségek?
 
Magyar nyelven válaszolj, legyél konkrét és tömör. Maximum 300 szó."""
 
    response = requests.post(GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 0.5
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
                        "👋 Üdvözöllek!\n\nÍrj be egy részvény nevét és összefoglalót küldök a legfrissebb hírek alapján.\n\nPéldák:\n• palantir\n• NVDA\n• tesla\n• microsoft")
                    continue
                
                print(f"Kérdés: {text}")
                send_telegram(chat_id, f"🔍 Keresem a <b>{text}</b> legfrissebb híreit...")
                
                # Hírek keresése
                news_text, news_links = search_news(text)
                
                if not news_text:
                    send_telegram(chat_id, f"❌ Nem találtam friss híreket erről: {text}")
                    continue
                
                # AI összefoglaló
                summary = get_stock_research(text, news_text)
                
                # Összefoglaló küldése
                send_telegram(chat_id, summary)
                
                # Linkek küldése
                if news_links:
                    links_message = "📰 <b>Forrás cikkek:</b>\n\n" + "\n\n".join(news_links)
                    send_telegram(chat_id, links_message)
                
                print(f"Válasz elküldve: {text}")
                
        except Exception as e:
            print(f"Hiba: {e}")
 
if __name__ == "__main__":
    main()
