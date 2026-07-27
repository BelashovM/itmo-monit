import requests
import json
import re
import os
from datetime import datetime

# ========== НАСТРОЙКИ ==========
URL = 'https://abit.itmo.ru/rating/master/budget/2397'
TELEGRAM_BOT_TOKEN = '7860640743:AAGq_jSWnY6gfm6i9BrnDrUiwl9I2cJDTyA'
TELEGRAM_CHAT_ID = '947777152'
DATA_FILE = 'itmo_data.json'
TRACKED_IDS = ['2129111', '2131095']
# ==================================

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
        }
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram отправлено")
            return True
        else:
            print(f"❌ Ошибка: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

def get_page():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(URL, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return None

def parse_data(html):
    if not html:
        return None
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        print("❌ JSON не найден")
        return None
    try:
        data = json.loads(match.group(1))
        general = data.get('props', {}).get('pageProps', {}).get('programList', {}).get('general_competition', [])
        applicants = []
        for item in general:
            applicants.append({
                'number': str(item.get('sspvo_id', '')),
                'position': item.get('position', 0),
                'priority': item.get('priority'),
                'test_type': item.get('exam_type', ''),
                'id_score': item.get('ia_scores', 0),
                'vi_score': item.get('exam_scores', 0),
                'total_score': item.get('total_scores', 0),
                'avg_score': item.get('diploma_average'),
                'consent': item.get('is_send_agreement', False)
            })
        print(f"✅ Найдено {len(applicants)} абитуриентов")
        return applicants
    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        return None

def analyze_data(applicants):
    tracked_info = {}
    for app in applicants:
        if app['number'] in TRACKED_IDS:
            tracked_info[app['number']] = {
                'position': app['position'],
                'priority': app['priority'],
                'id_score': app['id_score'],
                'vi_score': app['vi_score'],
                'total_score': app['total_score'],
                'avg_score': app['avg_score'],
                'consent': app['consent'],
                'test_type': app['test_type']
            }
    priority_1_count = sum(1 for app in applicants if app.get('priority') == 1)
    return tracked_info, priority_1_count, len(applicants)

def format_info(tracked_info, priority_1_count, total_count):
    lines = [
        "📊 СВОДКА ПО ИТМО",
        "═" * 25,
        f"👥 Всего: {total_count}",
        f"⭐ Приоритет 1: {priority_1_count}",
        ""
    ]
    for num, info in tracked_info.items():
        pos = info['position']
        medal = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else "📍"
        lines.append(f"🔹 №{num}")
        lines.append(f"   {medal} Позиция: {pos}")
        lines.append(f"   🎯 Приоритет: {info['priority']}")
        lines.append(f"   📝 ИД: {info['id_score']}")
        lines.append(f"   📊 Балл: {info['total_score']}")
        lines.append(f"   {'✅' if info['consent'] else '❌'} Согласие: {'Да' if info['consent'] else 'Нет'}")
        lines.append(f"   🔬 {info['test_type']}")
        lines.append("")
    return "\n".join(lines)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            print("⚠️ Файл поврежден, создаем новый")
            return None
    print("ℹ️ Файл данных не найден, первый запуск")
    return None

def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 Данные сохранены ({len(data)} записей)")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def main():
    print(f"🔄 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Проверка...")
    
    # ====== ВСЕГДА ОТПРАВЛЯЕМ ======
    send_telegram(f"🔄 Проверка в {datetime.now().strftime('%H:%M:%S')}")
    
    html = get_page()
    if not html:
        send_telegram("⚠️ Ошибка загрузки страницы ИТМО")
        return
    
    new_data = parse_data(html)
    if not new_data:
        send_telegram("⚠️ Ошибка парсинга страницы")
        return
    
    tracked_info, priority_1_count, total_count = analyze_data(new_data)
    old_data = load_data()
    summary = format_info(tracked_info, priority_1_count, total_count)
    
    # ====== ВСЕГДА ОТПРАВЛЯЕМ СВОДКУ ======
    send_telegram(summary)
    
    # Проверяем изменения
    if old_data:
        changes = []
        old_dict = {app['number']: app for app in old_data}
        for app in new_data:
            num = app['number']
            if num in old_dict:
                old = old_dict[num]
                if old.get('total_score') != app.get('total_score'):
                    changes.append(f"📊 №{num}: {old.get('total_score')} → {app.get('total_score')}")
                if old.get('position') != app.get('position'):
                    changes.append(f"📈 №{num}: {old.get('position')} → {app.get('position')}")
                if old.get('consent') != app.get('consent'):
                    changes.append(f"📋 №{num}: согласие {'✅' if app.get('consent') else '❌'}")
        
        if len(old_data) != len(new_data):
            send_telegram(f"🔔 ИЗМЕНИЛОСЬ КОЛИЧЕСТВО!\n{len(old_data)} → {len(new_data)}")
        elif changes:
            send_telegram("🔔 ИЗМЕНЕНИЯ!\n\n" + "\n".join(changes))
    else:
        print("✅ Первый запуск")
    
    save_data(new_data)
    print(f"💾 Данные сохранены ({len(new_data)} записей)")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        send_telegram(f"⚠️ Критическая ошибка: {e}")
        exit(1)
