#!/usr/bin/env python3
"""Monitora a BuyTicket e avisa quando aparecer Meia PCD ou Pista por até R$ X.

Uso:
    python3 bot.py                 # roda sem parar
    python3 bot.py --once          # checa uma vez e sai
    python3 bot.py --duration=1500 # roda por 25 min e sai (usado no GitHub Actions)
    python3 bot.py --test          # manda notificação de teste em todos os canais
    python3 bot.py --telegram-id   # descobre seu chat_id do Telegram
"""
import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = "https://buyticketbrasil.com"
API = BASE + "/api/backend/marketplaces"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
HERE = Path(__file__).resolve().parent
SEEN_FILE = HERE / "seen.json"


def load_config():
    cfg = {}
    path = HERE / "config.env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    cfg.update({k: v for k, v in os.environ.items() if k in cfg or k.startswith(("BOT_", "TELEGRAM_", "NTFY_"))})
    return cfg


CFG = load_config()
EVENT_SLUG = CFG.get("EVENT_SLUG", "hayleywilliams-saopaulo")
SESSION_ID = CFG.get("SESSION_ID", "e631d534-9b29-430c-a72a-9e8957aebd3f")
MAX_PRICE = float(CFG.get("MAX_PRICE", "300"))
INTERVAL = int(CFG.get("INTERVAL_SECONDS", "30"))
NTFY_TOPIC = CFG.get("NTFY_TOPIC", "")
TG_TOKEN = CFG.get("TELEGRAM_TOKEN", "")
TG_CHAT = CFG.get("TELEGRAM_CHAT_ID", "")
SESSION_URL = f"{BASE}/event/{EVENT_SLUG}/session/{SESSION_ID}"


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


class RateLimited(Exception):
    def __init__(self, wait):
        self.wait = wait


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            ra = e.headers.get("Retry-After", "")
            raise RateLimited(int(float(ra)) if ra.replace(".", "").isdigit() else 60)
        raise


def wanted(ticket_type, category):
    """Regra: qualquer setor 'Meia PCD', ou qualquer categoria de setor 'Pista'."""
    cat = category.lower()
    return ("pcd" in cat and "acompanhante" not in cat) or "pista" in ticket_type.lower()


def check():
    """Retorna lista de ofertas que batem com o filtro."""
    tickets = get_json(f"{API}/sessions/{SESSION_ID}/tickets")["tickets"]
    hits, cheapest = [], {}
    for t in tickets:
        cats = get_json(f"{API}/sessions/{SESSION_ID}/tickets/{t['ticketId']}/categories")["categories"]
        for c in cats:
            price = c["amount"]["value"]
            if not c.get("listingId") or price <= 0:
                continue
            if wanted(t["ticketType"], c["name"]):
                key = f"{t['ticketType']} · {c['name']}"
                cheapest[key] = price
                if price <= MAX_PRICE:
                    hits.append({
                        "setor": t["ticketType"],
                        "categoria": c["name"],
                        "preco": price,
                        "listingId": c["listingId"],
                        "link": f"{BASE}/checkout?listing={c['listingId']}",
                    })
        time.sleep(0.5)  # gentil com o servidor
    return hits, cheapest


# ---------- notificações ----------

def notify_mac(title, body):
    if sys.platform != "darwin":
        return
    try:
        safe = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(["osascript", "-e", f'display notification "{safe(body)}" with title "{safe(title)}" sound name "Glass"'], timeout=10)
        for _ in range(3):
            subprocess.run(["afplay", "/System/Library/Sounds/Sosumi.aiff"], timeout=10)
    except Exception as e:
        log(f"mac falhou: {e}")


def notify_ntfy(title, body, link):
    if not NTFY_TOPIC:
        return
    try:
        q = urllib.parse.urlencode({"title": title, "priority": "urgent", "tags": "rotating_light,ticket", "click": link})
        req = urllib.request.Request(f"https://ntfy.sh/{NTFY_TOPIC}?{q}", data=body.encode(), method="POST")
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        log(f"ntfy falhou: {e}")


def notify_telegram(text):
    if not (TG_TOKEN and TG_CHAT):
        return
    try:
        for chat in [c.strip() for c in TG_CHAT.split(",") if c.strip()]:
            data = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "true"}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=15).read()
    except Exception as e:
        log(f"telegram falhou: {e}")


def notify_all(title, body, link):
    log(f"🔔 {title} — {body}")
    notify_ntfy(title, body, link)
    notify_telegram(f"{title}\n{body}\n{link}")
    notify_mac(title, body)


# ---------- dedupe ----------

def load_seen():
    try:
        return json.loads(SEEN_FILE.read_text())
    except Exception:
        return {}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen))


def telegram_chat_id():
    if not TG_TOKEN:
        sys.exit("Coloque TELEGRAM_TOKEN no config.env primeiro.")
    data = get_json(f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates")
    ids = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "?") for u in data.get("result", []) if "message" in u}
    if not ids:
        print("nenhum — mande uma mensagem pro seu bot no Telegram e rode de novo")
    for i, n in ids.items():
        print(f"{n}: {i}")
    if ids:
        print("Coloque no config.env: TELEGRAM_CHAT_ID=" + ",".join(str(i) for i in ids))


def main():
    args = set(sys.argv[1:])
    if "--telegram-id" in args:
        return telegram_chat_id()
    if "--test" in args:
        return notify_all("Teste do bot de ingresso", "Se você viu isso, o aviso funciona ✅", SESSION_URL)

    log(f"Monitorando {SESSION_URL}")
    log(f"Filtro: Meia PCD (qualquer setor) ou Pista · até R$ {MAX_PRICE:.0f} · a cada ~{INTERVAL}s")
    deadline = None
    for a in sys.argv[1:]:
        if a.startswith("--duration="):
            deadline = time.time() + int(a.split("=", 1)[1])
    log(f"Canais: Mac {'✅' if sys.platform == 'darwin' else '❌'} · ntfy {'✅' if NTFY_TOPIC else '❌'} · Telegram {'✅' if TG_TOKEN and TG_CHAT else '❌'}")
    seen = load_seen()
    errors = 0
    while deadline is None or time.time() < deadline:
        try:
            hits, cheapest = check()
            errors = 0
            for h in hits:
                key = f"{h['listingId']}:{h['preco']}"
                if key in seen:
                    continue
                seen[key] = time.time()
                save_seen(seen)
                notify_all(f"🎟️ {h['setor']} {h['categoria']} R$ {h['preco']:.0f}",
                           f"{h['setor']} · {h['categoria']} por R$ {h['preco']:.2f}. Corre!", h["link"])
            resumo = ", ".join(f"{k} R${v:.0f}" for k, v in sorted(cheapest.items(), key=lambda x: x[1])) or "nada no filtro"
            log(f"{'✅ ' + str(len(hits)) + ' oferta(s)' if hits else 'nada ≤ R$' + str(int(MAX_PRICE))} | menores: {resumo}")
            if "--once" in args:
                return
            time.sleep(INTERVAL + random.uniform(0, 10))
        except RateLimited as e:
            log(f"Site pediu pra esperar (429). Pausando {e.wait}s.")
            time.sleep(e.wait)
        except KeyboardInterrupt:
            log("Parado.")
            return
        except Exception as e:
            errors += 1
            wait = min(300, 15 * errors)
            log(f"Erro ({type(e).__name__}: {e}). Tentando de novo em {wait}s.")
            if errors == 10:
                notify_all("⚠️ Bot de ingresso com erro", f"10 erros seguidos: {e}", SESSION_URL)
            if "--once" in args:
                return
            time.sleep(wait)


if __name__ == "__main__":
    main()
