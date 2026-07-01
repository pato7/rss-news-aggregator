# 📰 Daily News RSS Aggregator

Automatizovaný generátor jedného denného sumarizovaného RSS feedu pre AI a IT v slovenčine.

## 🌟 Ako to funguje?
1. Každé ráno o **06:00 UTC** automatický GitHub workflow stiahne články zo zadaných zdrojov.
2. Cez **OpenRouter API (Gemini 2.5 Flash / Llama 3.3)** AI vyfiltruje balast, deduplikuje témy a vyberie **TOP 10 najvýznamnejších správ** pre každú kategóriu.
3. Vygeneruje **jediný RSS feed** `daily-news.xml`, kde každá kategória predstavuje samostatnú dennú správu (napr. *AI: denné novinky za 29. 06. 2026*).

---

## 🔗 Váš Jednotný RSS Feed
Vložte si do vašej RSS čítačky túto jedinú adresu:

📡 **`https://pato7.github.io/rss-news-aggregator/daily-news.xml`**
