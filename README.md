# ingresso-bot

Monitora a BuyTicket e avisa (Telegram, ntfy, Mac) quando aparecer Meia PCD ou Pista por até R$400.

- Local: copie `config.example.env` para `config.env`, preencha e rode `python3 bot.py`.
- Nuvem: GitHub Actions (`.github/workflows/monitor.yml`) roda a cada 5 min usando os secrets
  `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `NTFY_TOPIC`.
