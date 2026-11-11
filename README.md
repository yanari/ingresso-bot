# ingresso-bot

Monitora a BuyTicket e avisa (Telegram, ntfy, Mac) quando aparecer **Meia PCD** ou **Meia Estudante** (qualquer setor) por até **R$400**,
nos shows da Hayley Williams em São Paulo dos dias **12/11** e **13/11**.

- Local: copie `config.example.env` para `config.env`, preencha e rode `python3 bot.py`.
- Nuvem: GitHub Actions (`.github/workflows/monitor.yml`) roda a cada 5 min usando os secrets
  `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `NTFY_TOPIC`.
