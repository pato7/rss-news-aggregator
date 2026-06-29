# 📰 AI & IT Daily RSS Aggregator

Automatizovaný generátor denného sumarizovaného prehľadu najdôležitejších správ z oblasti AI a IT v slovenčine.

## 🌟 Ako to funguje?
1. Každé ráno o **06:00 UTC** automatický GitHub workflow stiahne články zo zadaných zdrojov (ArXiv, HackerNews, TechCrunch...).
2. Cez **OpenRouter API (Gemini 2.5 Flash / Llama 3.3)** AI vyfiltruje balast, deduplikuje témy a vyberie **TOP 10 najvýznamnejších správ**.
3. Pre každú správu vygeneruje výstižný slovenský sumarizačný text a uloží ho do RSS feedu.
4. Výsledný RSS feed publikuje na **GitHub Pages**, odkiaľ si ho môžete odoberať v ľubovoľnej RSS čítačke.

---

## 🔗 Vaše RSS Feedy (po sprevádzkovaní)
Vymeňte `<vase-pouzivatelske-meno>` za vaše meno na GitHube:

* **AI Novinky:** `https://<vase-pouzivatelske-meno>.github.io/rss-news-aggregator/ai.xml`
* **IT Novinky:** `https://<vase-pouzivatelske-meno>.github.io/rss-news-aggregator/it.xml`

---

## 🚀 Návod na sprevádzkovanie (3 kroky)

### 1. Krok: Vytvorenie OpenRouter API kľúča
1. Prejdite na [openrouter.ai](https://openrouter.ai/) a prihláste sa / zaregistrujte sa.
2. V sekcii **Keys** vytvorte nový kľúč (napr. s názvom `RSS Generator`).
3. Kľúč si skopírujte.

### 2. Krok: Vytvorenie repozitára a vloženie súborov
1. Prejdite na [github.com/new](https://github.com/new) a vytvore nový **Public** repozitár s názvom `rss-news-aggregator`.
2. Nahrajte doň všetky súbory z tohto priečinka (buď cez Git príkazový riadok alebo jednoduchým pretiahnutím súborov na webe GitHubu).

### 3. Krok: Nastavenie GitHub Secrets a Pages
1. Vo vašom repozitári na GitHube kliknite na **Settings** -> **Secrets and variables** -> **Actions**.
2. Kliknite na **New repository secret**:
   * Name: `OPENROUTER_API_KEY`
   * Secret: *(vložte váš skopírovaný OpenRouter kľúč)*
3. Kliknite na **Settings** -> **Pages** (v ľavom menu):
   * Build and deployment -> Source: zvoľte **Deploy from a branch**.
   * Branch: zvoľte **gh-pages** (táto vetva sa automaticky vytvorí po prvom spustení workflowu) a priečinok `/ (root)`.
   * Uložte (Save).

---

## 🧪 Manuálne testovacie spustenie
Nemusíte čakať do rána! Vo vašom repozitári kliknite na záložku **Actions**, zvoľte **Daily AI & IT RSS Generator** a kliknite na tlačidlo **Run workflow**. O cca 1 minútu bude váš RSS feed vygenerovaný a dostupný!
