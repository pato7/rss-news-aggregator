import os
import sys
import json
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
    
    for url in sources:
        try:
            print(f"Stahujem feed: {url}")
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                link = getattr(entry, "link", "")
                title = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", getattr(entry, "description", "")).strip()
                
                if not link or not title or link in seen_urls:
                    continue
                    
                seen_urls.add(link)
                # Skracenie obsahu pre prompt
                clean_summary = summary.replace("\n", " ")[:300]
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

def summarize_with_llm(client, category_title, articles, config):
    if not articles:
        return []
        
    model = config.get("openrouter_model", "google/gemini-2.5-flash")
    fallback_model = config.get("fallback_model", "meta-llama/llama-3.3-70b-instruct")
    max_items = config.get("max_items_per_category", 10)
    
    system_prompt = (
        "Si spickovy IT a AI sefredaktor. Tvojou úlohou je vybrat a zhrnut najdolezitejsie spravy z oboru.\n"
        f"Dostanes zoznam dnesnych clankov. Vyber z nich presne TOP {max_items} najvyznamnejsich a najzasadnejsich sprav.\n"
        "Pravidla:\n"
        "1. Ak viacero clankov pise o tej istej teme/udalosti, spoj ich do jednej spravy (deduplikuj).\n"
        "2. Vyber len spravy s realnym dopadom, ignoruj balast a sponzorovany obsah.\n"
        "3. Pre kazdy vybrany clanok napis vystizny sumarizacny popis v slovencine (2 az 4 vety).\n"
        "4. ODPOVEDAJ VYHRADNE VO FORMATE JSON ako pole objektov bez akehokolvek dalsieho textu alebo markdown obalov (vyhnij sa ```json obalom, vrat len cisty JSON array).\n\n"
        "Format objektu:\n"
        "[\n"
        '  {\n'
        '    "title": "Nazov spravy v slovencine",\n'
        '    "link": "Povodny odkaz na najrelevantnejsi clanok",\n'
        '    "summary": "Strucny a vystizny sumar doležitosti v slovencine."\n'
        '  }\n'
        "]"
    )
    
    user_content = f"Kategoria: {category_title}\nZoznam stiahnutych clankov ({len(articles)}):\n"
    for idx, a in enumerate(articles, 1):
        user_content += f"{idx}. Titul: {a['title']}\n   Link: {a['link']}\n   Snippet: {a['summary_raw']}\n\n"

    def make_api_call(selected_model):
        print(f"Volam OpenRouter API s modelom: {selected_model}...")
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3,
            max_tokens=3000
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
        return json.loads(content)

    try:
        return make_api_call(model)
    except Exception as e:
        print(f"Chyba pri primarnom modeli {model}: {e}. Skusam fallback model: {fallback_model}...")
        try:
            return make_api_call(fallback_model)
        except Exception as e2:
            print(f"Kriticka chyba pri LLM spracovani: {e2}")
            return []

def generate_rss_xml(category, items, output_path):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    ET.SubElement(channel, "title").text = category["title"]
    ET.SubElement(channel, "description").text = category["description"]
    ET.SubElement(channel, "link").text = f"https://github.com/rss-aggregator/{category['id']}"
    ET.SubElement(channel, "language").text = "sk"
    ET.SubElement(channel, "pubDate").text = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    for item in items:
        entry = ET.SubElement(channel, "item")
        ET.SubElement(entry, "title").text = item.get("title", "Bez nazvu")
        ET.SubElement(entry, "link").text = item.get("link", "")
        ET.SubElement(entry, "description").text = item.get("summary", "")
        ET.SubElement(entry, "guid").text = item.get("link", "")
        ET.SubElement(entry, "pubDate").text = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        
    xml_str = ET.tostring(rss, encoding="utf-8")
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(pretty_xml)
    print(f"RSS feed uspesne vygenerovany: {output_path}")

def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("UPOZORNENIE: Chyba OPENROUTER_API_KEY v premennych prostredia!")
        sys.exit(1)
        
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )
    
    config = load_config()
    public_dir = "public"
    os.makedirs(public_dir, exist_ok=True)
    
    for cat in config.get("categories", []):
        print(f"\n--- Spracovavam kategoriu: {cat['title']} ---")
        articles = fetch_category_articles(cat["sources"])
        print(f"Celkovo najdenych clankov: {len(articles)}")
        
        curated_items = summarize_with_llm(client, cat["title"], articles, config)
        out_file = os.path.join(public_dir, f"{cat['id']}.xml")
        generate_rss_xml(cat, curated_items, out_file)

if __name__ == "__main__":
    main()
