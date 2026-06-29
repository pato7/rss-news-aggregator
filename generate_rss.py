import os
import sys
import json
import re
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import yaml
import feedparser
import requests
from openai import OpenAI

def load_config(config_path="config.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def fetch_category_articles(sources, max_per_source=15):
    articles = []
    seen_urls = set()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    for url in sources:
        try:
            print(f"Stahujem feed: {url}")
            resp = requests.get(url, headers=headers, timeout=15)
            feed = feedparser.parse(resp.content)
            
            count = 0
            for entry in feed.entries:
                link = getattr(entry, "link", "")
                title = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", getattr(entry, "description", "")).strip()
                
                if not link or not title or link in seen_urls:
                    continue
                    
                seen_urls.add(link)
                clean_summary = re.sub('<[^<]+?>', '', summary).replace("\n", " ").strip()[:300]
                articles.append({
                    "title": title,
                    "link": link,
                    "summary_raw": clean_summary
                })
                count += 1
                if count >= max_per_source:
                    break
        except Exception as e:
            print(f"Chyba pri stahovani {url}: {e}")
            
    return articles

def parse_json_from_response(content):
    content = content.strip()
    if "```" in content:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if match:
            content = match.group(1).strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start_arr = content.find("[")
        end_arr = content.rfind("]")
        if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
            try:
                data = json.loads(content[start_arr:end_arr+1])
            except json.JSONDecodeError:
                data = []
        else:
            data = []
            
    if isinstance(data, dict):
        for key in ["items", "articles", "news", "data", "results"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        return []
    elif isinstance(data, list):
        return data
    return []

def summarize_with_llm(client, category, articles, config):
    if not articles:
        return []
        
    category_id = category["id"]
    category_title = category["title"]
    model = config.get("openrouter_model", "google/gemini-2.5-flash")
    fallback_model = config.get("fallback_model", "meta-llama/llama-3.3-70b-instruct")
    max_items = config.get("max_items_per_category", 10)
    
    category_instructions = ""
    if category_id == "it":
        category_instructions = (
            "DÔLEŽITÉ: Týka sa to výhradne IT noviniek. PRÍSNE VYFILTRUJ a vynechaj všetky správy týkajúce sa umelej inteligencie (AI, LLM, ChatGPT, Machine Learning aj GPU pre AI), "
            "keďže AI má vlastnú samostatnú kategóriu! Zameraj sa výhradne na klasické IT, softvérové inžinierstvo, kyberbezpečnosť, operačné systémy, cloud, hardware a tech biznis.\n"
        )
    elif category_id == "ai":
        category_instructions = (
            "DÔLEŽITÉ: Zameraj sa výhradne na novinky z oboru Umelá inteligencia (AI, LLM, Machine Learning, výskumné modely, AI nástroje a AI výpočtovú infraštruktúru).\n"
        )
    
    system_prompt = (
        "Si spickovy IT a AI sefredaktor. Tvojou ulohou je vybrat a zhrnut najdolezitejsie spravy z oboru.\n"
        f"Dostanes zoznam dnesnych clankov pre kategóriu '{category_title}'. Vyber z nich presne TOP {max_items} najvyznamnejsich a najzasadnejsich sprav.\n"
        f"{category_instructions}"
        "Pravidla:\n"
        "1. Ak viacero clankov pise o tej istej teme/udalosti, spoj ich do jednej spravy (deduplikuj).\n"
        "2. Vyber len spravy s realnym dopadom, ignoruj balast a sponzorovany obsah.\n"
        "3. Pre kazdy vybrany clanok napis vystizny sumarizacny popis v slovencine (2 az 4 vety).\n"
        "4. ODPOVEDAJ VYHRADNE VO FORMATE JSON ako pole objektov bez akehokolvek dalsieho textu okolo.\n\n"
        "Format objektu:\n"
        "[\n"
        '  {\n'
        '    "title": "Nazov spravy v slovencine",\n'
        '    "link": "Povodny odkaz na najrelevantnejsi clanok",\n'
        '    "summary": "Strucny a vystizny sumar dolezitosti v slovencine."\n'
        '  }\n'
        "]"
    )
    
    user_content = f"Kategoria: {category_title}\nZoznam stiahnutych clankov ({len(articles)}):\n"
    for idx, a in enumerate(articles[:40], 1):
        user_content += f"{idx}. Titul: {a['title']}\n   Link: {a['link']}\n   Snippet: {a['summary_raw']}\n\n"

    def make_api_call(selected_model):
        print(f"Volam OpenRouter API s modelom: {selected_model} pre kategóriu {category_id}...")
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3,
            max_tokens=3000,
            extra_headers={
                "HTTP-Referer": "https://github.com/pato7/rss-news-aggregator",
                "X-Title": "AI & IT Daily RSS Aggregator"
            }
        )
        content = response.choices[0].message.content
        return parse_json_from_response(content)

    try:
        result = make_api_call(model)
        if result:
            return result
        print("Primarny model vratil prazdny vysledok, skusam fallback...")
    except Exception as e:
        print(f"Chyba pri primarnom modeli {model}: {e}. Skusam fallback model: {fallback_model}...")
        
    try:
        return make_api_call(fallback_model)
    except Exception as e2:
        print(f"Kriticka chyba pri LLM spracovani: {e2}")
        return []

def generate_unified_rss(categories_data, output_path):
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_str = now_dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
    today_display = now_dt.strftime("%d. %m. %Y")
    today_iso = now_dt.strftime("%Y-%m-%d")
    
    existing_items = []
    today_guids = set()
    for cat in categories_data:
        today_guids.add(f"digest-{cat['id']}-{today_iso}")

    if os.path.exists(output_path):
        try:
            tree = ET.parse(output_path)
            root = tree.getroot()
            channel_elem = root.find("channel")
            if channel_elem is not None:
                for item_elem in channel_elem.findall("item"):
                    guid_elem = item_elem.find("guid")
                    guid_val = guid_elem.text if guid_elem is not None else ""
                    if guid_val not in today_guids:
                        existing_items.append(item_elem)
        except Exception as e:
            print(f"Poznamka: Nepodarilo sa nacitat stavajuce RSS, vytvaram nove ({e})")

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    ET.SubElement(channel, "title").text = "Denné novinky"
    # Zmena slovneho spojenia oborov -> oblasti
    ET.SubElement(channel, "description").text = "Jednotný denný sumarizovaný prehľad najvýznamnejších správ z rôznych oblastí."
    ET.SubElement(channel, "link").text = "https://pato7.github.io/rss-news-aggregator/daily-news.xml"
    ET.SubElement(channel, "language").text = "sk"
    ET.SubElement(channel, "pubDate").text = now_str
    
    new_items_count = 0
    for cat in categories_data:
        items = cat["curated_items"]
        cat_id_upper = cat["id"].upper()
        
        if isinstance(items, list) and len(items) > 0:
            daily_entry = ET.SubElement(channel, "item")
            ET.SubElement(daily_entry, "title").text = f"{cat_id_upper}: denné novinky za {today_display}"
            ET.SubElement(daily_entry, "link").text = f"https://pato7.github.io/rss-news-aggregator/daily-news.xml#{cat['id']}-{today_iso}"
            ET.SubElement(daily_entry, "guid").text = f"digest-{cat['id']}-{today_iso}"
            ET.SubElement(daily_entry, "pubDate").text = now_str
            
            html_parts = [f"<h2>{cat['title']} – {today_display}</h2>", "<ol style='line-height: 1.6;'>"]
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "Bez nazvu"))
                link = str(item.get("link", "#"))
                summary = str(item.get("summary", ""))
                
                html_parts.append(
                    f"<li style='margin-bottom: 18px;'>"
                    f"<strong><a href='{link}' target='_blank' style='font-size: 16px; color: #1a0dab;'>{title}</a></strong><br/>"
                    f"<span style='color: #333;'>{summary}</span>"
                    f"</li>"
                )
            html_parts.append("</ol>")
            
            ET.SubElement(daily_entry, "description").text = "".join(html_parts)
            new_items_count += 1

    for prev_item in existing_items[:60]:
        channel.append(prev_item)
        
    xml_str = ET.tostring(rss, encoding="utf-8")
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(pretty_xml)
    print(f"Jednotny RSS feed uspesne vygenerovany ({new_items_count} novych poloziek): {output_path}")

def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("KRITICKA CHYBA: Chyba OPENROUTER_API_KEY v premennych prostredia!")
        sys.exit(1)
        
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )
    
    config = load_config()
    public_dir = "public"
    os.makedirs(public_dir, exist_ok=True)
    
    categories_data = []
    for cat in config.get("categories", []):
        print(f"\n--- Spracovavam kategoriu: {cat['title']} ---")
        articles = fetch_category_articles(cat["sources"])
        print(f"Celkovo najdenych clankov: {len(articles)}")
        
        curated_items = summarize_with_llm(client, cat, articles, config)
        cat_copy = dict(cat)
        cat_copy["curated_items"] = curated_items
        categories_data.append(cat_copy)

    master_out_file = os.path.join(public_dir, "daily-news.xml")
    generate_unified_rss(categories_data, master_out_file)

if __name__ == "__main__":
    main()
