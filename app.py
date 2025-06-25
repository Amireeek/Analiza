# -*- coding: utf-8 -*-

# ==============================================================================
# Krok 0: Instalacja bibliotek
# ==============================================================================
# pip install streamlit requests trafilatura google-generativeai scrapingbee
# ==============================================================================
# Krok 1: Import bibliotek
# ==============================================================================
import streamlit as st
import requests
import re
from trafilatura import extract
import google.generativeai as genai
from urllib.parse import urlencode as encode_query_params
import json
import time # Do ewentualnych opóźnień między wywołaniami API

# ==============================================================================
# Krok 2: Konfiguracja strony Streamlit
# ==============================================================================
st.set_page_config(page_title="SEO Content Powerhouse", page_icon="🚀", layout="wide")
st.title("🚀 SEO Content Powerhouse z AI")
st.markdown("Narzędzie do tworzenia kompletnych strategii contentowych na podstawie analizy TOP 10 wyników Google.")

# ==============================================================================
# Krok 3: Obsługa Kluczy API ze Streamlit Secrets
# ==============================================================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SCRAPINGBEE_API_KEY = st.secrets["SCRAPINGBEE_API_KEY"]
    DATAFORSEO_LOGIN = st.secrets["DATAFORSEO_LOGIN"]
    DATAFORSEO_PASSWORD = st.secrets["DATAFORSEO_PASSWORD"]

    genai.configure(api_key=GEMINI_API_KEY)

except KeyError as e:
    missing_key = str(e).strip("'")
    st.error(f"🛑 Błąd konfiguracji sekretów! Nie znaleziono wymaganego sekretu: {missing_key}. Upewnij się, że skonfigurowałeś GEMINI_API_KEY, SCRAPINGBEE_API_KEY, DATAFORSEO_LOGIN i DATAFORSEO_PASSWORD.")
    st.stop()
except Exception as e:
    st.error(f"🛑 Wystąpił nieoczekiwany błąd podczas ładowania kluczy: {e}")
    st.stop()

# ==============================================================================
# Krok 4: Funkcje Backendowe
# ==============================================================================

@st.cache_data
def get_serp_data_with_dataforseo(login, password, query, num_results=10, location_code=2616, language_code='pl'):
    """Pobiera wyniki wyszukiwania Google (organiczne i AI Overview) używając API DataForSEO."""
    # (bez zmian - usunięto tylko komentarze st.write)
    post_data = [{"keyword": query, "location_code": location_code, "language_code": language_code, "depth": num_results}]
    headers = {'Content-Type': 'application/json'}
    endpoint_url = "https://api.dataforseo.com/v3/serp/google/organic/live/regular"
    organic_results_list, ai_overview_text_content = [], None
    try:
        response = requests.post(endpoint_url, auth=(login, password), headers=headers, json=post_data, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data.get("status_code") == 20000 and data.get("tasks") and data["tasks"][0].get("result") and data["tasks"][0]["result"][0].get("items"):
            items = data["tasks"][0]["result"][0]["items"]
            for item in items:
                item_type = item.get("type")
                if item_type == "organic":
                    title, link = item.get("title"), item.get("url")
                    if title and link: organic_results_list.append({'title': title, 'link': link})
                elif item_type == "ai_overview":
                    if item.get("text"): ai_overview_text_content = item.get("text")
                    elif item.get("description"): ai_overview_text_content = item.get("description")
                    elif item.get("paragraphs") and isinstance(item.get("paragraphs"), list):
                        ai_overview_text_content = "\n\n".join([p.get("text", "") for p in item.get("paragraphs") if p.get("text")])
        else:
            status_message = data.get("status_message", "Nieznany błąd.")
            tasks_error = ""
            if data.get("tasks") and data["tasks"][0].get("status_message") != "Ok.":
                tasks_error = f" Błąd zadania: {data['tasks'][0]['status_code']} - {data['tasks'][0]['status_message']}"
            st.warning(f"DataForSEO API zwróciło nieoczekiwany status lub brak wyników: {status_message}{tasks_error}.")
        return {'organic_results': organic_results_list, 'ai_overview_text': ai_overview_text_content}
    except: return {'organic_results': [], 'ai_overview_text': None} # Uproszczona obsługa błędów

@st.cache_data
def scrape_and_clean_content(url_to_scrape, scrapingbee_api_key):
    """Pobiera i czyści treść ze strony używając ScrapingBee."""
    # (bez zmian)
    try:
        response = requests.get(
            url='https://app.scrapingbee.com/api/v1/',
            params={'api_key': scrapingbee_api_key, 'url': url_to_scrape, 'premium_proxy': 'true', 'block_resources': 'false'},
            timeout=90
        )
        response.raise_for_status()
        extracted_text = extract(response.text, include_comments=False, include_tables=False, include_images=False)
        if not extracted_text: return None
        cleaned_text = re.sub(r'\s+', ' ', extracted_text).strip()
        return cleaned_text if len(cleaned_text) > 100 else None
    except: return None

# --- NOWE FUNKCJE GENERUJĄCE KAŻDĄ SEKCJĘ RAPORTU ---
def generate_gemini_response(section_prompt, section_name):
    """Wysyła pojedynczy prompt do Gemini i zwraca odpowiedź."""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        generation_config = genai.types.GenerationConfig(max_output_tokens=8192)
        response = model.generate_content(section_prompt, generation_config=generation_config)
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
        else:
            st.warning(f"⚠️ Gemini zwróciło pustą odpowiedź dla sekcji: {section_name}.")
            if hasattr(response, 'prompt_feedback'): st.write(f"Feedback dla {section_name}:", response.prompt_feedback)
            if hasattr(response, 'candidates') and response.candidates and response.candidates[0].finish_reason:
                 st.write(f"Przyczyna zakończenia dla {section_name}:", response.candidates[0].finish_reason)
            return f"### {section_name}\nBrak danych od AI dla tej sekcji."
    except Exception as e:
        st.error(f"🛑 Błąd komunikacji z Gemini API dla sekcji {section_name}: {e}")
        return f"### {section_name}\nBłąd generowania tej sekcji."

def generate_kluczowe_punkty(all_content, keyword_phrase):
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 1. Kluczowe Punkty Wspólne".
Wypunktuj tematy, podtematy, kluczowe informacje, perspektywy i style narracji, które powtarzają się w większości analizowanych tekstów. Skup się na tym, co jest standardem i skonstruuj wytyczne dla copywritera. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 1. Kluczowe Punkty Wspólne`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "1. Kluczowe Punkty Wspólne")

def generate_unikalne_elementy(all_content, keyword_phrase):
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 2. Unikalne i Wyróżniające Się Elementy".
Wypunktuj nietypowe, oryginalne, innowacyjne lub szczególnie wartościowe informacje, dane, przykłady, case studies, infografiki (opisz co przedstawiają) lub perspektywy, które pojawiły się tylko w niektórych źródłach z TOP10 i mogą stanowić przewagę konkurencyjną dla nowego artykułu. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 2. Unikalne i Wyróżniające Się Elementy`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "2. Unikalne i Wyróżniające Się Elementy")

def generate_słowa_kluczowe(all_content, keyword_phrase):
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 3. Sugerowane Słowa Kluczowe i Semantyka".
Na podstawie analizy treści konkurencji z TOP10, stwórz listę 10-12 najważniejszych słów kluczowych, fraz długoogonowych i pojęć semantycznie powiązanych. Pogrupuj je tematycznie, jeśli to ułatwia zrozumienie. Wskaż intencję wyszukiwania dla frazy głównej. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 3. Sugerowane Słowa Kluczowe i Semantyka`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "3. Sugerowane Słowa Kluczowe i Semantyka")

def generate_struktura_artykulu(all_content, keyword_phrase):
    prompt = f"""Jako ekspert SEO specjalizujący się w tworzeniu szczegółowych konspektów, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 4. Proponowana Struktura Artykułu (Szkic)".
Zaproponuj BARDZO ROZBUDOWANĄ i SZCZEGÓŁOWĄ strukturę nowego artykułu w formacie Markdown. Struktura MUSI zawierać **DOKŁADNIE 5 (pięć) głównych sekcji (nagłówki H2)**. Dla **KAŻDEJ z tych pięciu głównych sekcji (H2) zaproponuj DOKŁADNIE 3 (trzy) bardziej szczegółowe podpunkty (nagłówki H3)**. Nagłówki powinny być angażujące i precyzyjnie opisywać zawartość. Uwzględnij kluczowe punkty, unikalne elementy i semantykę z analizy. Podaj także 2-3 chwytliwe tytuły dla całego artykułu na początku tej sekcji, przed strukturą. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 4. Proponowana Struktura Artykułu (Szkic)`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "4. Proponowana Struktura Artykułu (Szkic)")

def generate_faq(all_content, keyword_phrase):
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 5. Sekcja FAQ (Pytania i Odpowiedzi)".
Stwórz listę 4-5 najczęstszych pytań, na które odpowiadają konkurenci z TOP10, w stylu 'People Also Ask'. **Dla każdego pytania, podaj 2-3 zdaniową bezpośrednią odpowiedź, pisząc ją BEZPOŚREDNIO POD DANYM PYTANIEM, w nowej linii.** Użyj formatowania Markdown: pytanie jako zwykły tekst lub pogrubiony, a odpowiedź pod nim. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 5. Sekcja FAQ (Pytania i Odpowiedzi)`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "5. Sekcja FAQ (Pytania i Odpowiedzi)")

def generate_wskazowki_sge(all_content, keyword_phrase, ai_overview_text=None):
    ai_overview_instructions = ""
    if ai_overview_text:
        ai_overview_instructions = f"""Przeanalizuj poniższy tekst AI Overview wygenerowany przez Google dla frazy "{keyword_phrase}":
---
{ai_overview_text}
---
Na podstawie tej analizy oraz Twojej wiedzy o SEO, sformułuj 5-7 konkretnych, praktycznych wskazówek dla twórców treści. Wskazówki powinny wyjaśniać, jakie elementy w ich własnych treściach mogłyby zwiększyć prawdopodobieństwo, że Google wykorzysta ich materiały do generowania podobnych AI Overviews. Skup się na tym, co można zrobić, aby treść była "SGE-friendly".
"""
    else:
        ai_overview_instructions = f"""Dla frazy "{keyword_phrase}" nie znaleziono AI Overview. 
Mimo to, na podstawie analizy treści z artykułów TOP10 (dostarczonych poniżej), zidentyfikuj cechy tych treści, które mogłyby być korzystne z punktu widzenia generowania AI Overviews (SGE) przez Google. Podaj 5-7 praktycznych wskazówek SEO, jak na podstawie tych najlepszych artykułów z TOP10 można tworzyć treści "SGE-friendly".
"""
    prompt = f"""Jako analityk SEO, Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 6. Wskazówki SEO dla AI Overviews (SGE)".
{ai_overview_instructions}
Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 6. Wskazówki SEO dla AI Overviews (SGE)`.

Treść z artykułów TOP10 do analizy (jeśli potrzebna i nie było AI Overview):
{all_content if not ai_overview_text and all_content else "Analiza bazuje głównie na dostarczonym AI Overview lub generuje ogólne porady."}
"""
    return generate_gemini_response(prompt, "6. Wskazówki SEO dla AI Overviews (SGE)")


def parse_report(report_text):
    """Dzieli pełny raport na sekcje do wyświetlenia w zakładkach."""
    # (bez zmian)
    if not report_text: return {}
    sections = {}
    # Regex zmodyfikowany, aby lepiej pasował do pojedynczych sekcji zwracanych przez AI
    pattern = r"###\s*(?:\d+\.\s*)?(.*?)\n(.*?)(?=\n###\s*\d+\.|$|\Z)" # Zmiana: $ na końcu, aby łapać ostatnią sekcję
    matches = re.findall(pattern, report_text, re.DOTALL)
    for match in matches:
        title = match[0].strip()
        content = match[1].strip()
        if title and content: # Dodano warunek, by content nie był pusty
            sections[title] = content
    return sections

# ==============================================================================
# Krok 5: Interfejs Użytkownika i główna logika
# ==============================================================================
keyword = st.text_input("Wprowadź frazę kluczową, którą chcesz przeanalizować:", placeholder="np. jak dbać o buty skórzane")

if st.button("🚀 Wygeneruj Kompleksowy Audyt SEO"):
    if not keyword:
        st.warning("Proszę wpisać frazę kluczową.")
        st.stop()

    if 'SCRAPINGBEE_API_KEY' not in st.secrets or \
       'GEMINI_API_KEY' not in st.secrets or \
       'DATAFORSEO_LOGIN' not in st.secrets or \
       'DATAFORSEO_PASSWORD' not in st.secrets:
         st.error("Błąd: Nie wszystkie wymagane klucze API są skonfigurowane w Streamlit Secrets.")
         st.stop()

    with st.spinner("Przeprowadzam pełny audyt... To może potrwać kilka minut."):
        st.info("Etap 1/4: Pobieranie i filtrowanie wyników z Google (przez DataForSEO)...")
        serp_data = get_serp_data_with_dataforseo(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD, keyword)
        top_results, ai_overview_text_from_serp = [], None
        if serp_data:
            top_results = serp_data.get('organic_results', [])
            ai_overview_text_from_serp = serp_data.get('ai_overview_text')
        
        if not top_results and not ai_overview_text_from_serp:
            st.error("Nie udało się pobrać żadnych danych SERP. Audyt przerwany.")
            st.stop()
        if not top_results:
            st.warning(f"Nie znaleziono wyników organicznych dla '{keyword}'. Analiza będzie kontynuowana, jeśli znaleziono AI Overview.")

        BANNED_DOMAINS = ["youtube.com", "pinterest.", "instagram.com", "facebook.com", "olx.pl", "allegro.pl", "twitter.com", "tiktok.com", "wikipedia.org", "słownik.pl", "encyklopedia.", "forum.", ".gov", ".edu", "otodom.pl", "gratka.pl", "domiporta.pl"]
        filtered_results = [r for r in top_results if r and r.get('link') and not any(b in r['link'].lower() for b in BANNED_DOMAINS)]

        if not filtered_results and not ai_overview_text_from_serp:
             st.error("Po filtracji brak artykułów i AI Overview do analizy.")
             st.stop()
        elif not filtered_results and ai_overview_text_from_serp:
             if ai_overview_text_from_serp: st.info("Brak artykułów po filtracji, ale jest AI Overview. Przechodzę do analizy AI.")
        elif filtered_results:
             if len(top_results) > len(filtered_results):
                  st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników, analizuję {len(filtered_results)} artykułów.")
             st.subheader("Analizowane adresy URL (po filtracji):")
             for i, r in enumerate(filtered_results, 1): st.write(f"{i}. [{r.get('title', r.get('link'))}]({r.get('link', '#')})")

        all_articles_content_str = ""
        if filtered_results:
            st.info("Etap 2/4: Pobieranie treści ze stron (ScrapingBee)...")
            all_articles_content_list = []
            progress_bar = st.progress(0)
            for i, result in enumerate(filtered_results):
                url = result.get('link')
                if url:
                    content = scrape_and_clean_content(url, SCRAPINGBEE_API_KEY)
                    if content: all_articles_content_list.append(content)
                    progress_bar.progress((i + 1) / len(filtered_results))
            progress_bar.empty()
            if not all_articles_content_list: st.warning("Nie udało się pobrać treści z żadnej ze stron.")
            else:
                st.success(f"✅ Pomyślnie pobrano treści z {len(all_articles_content_list)} stron.")
                all_articles_content_str = "\n\n---\n\n".join(all_articles_content_list)
        
        if not all_articles_content_str and not ai_overview_text_from_serp:
            st.error("Brak treści artykułów oraz brak AI Overview do analizy. Audyt przerwany.")
            st.stop()

        # --- ZMIANA TUTAJ: Generowanie raportu sekcja po sekcji ---
        st.info("Etap 3/4: Generowanie raportu przez AI (Gemini) - sekcja po sekcji...")
        
        report_parts = []
        report_progress = st.progress(0)
        total_sections = 6

        # Definicje funkcji i kolejność wywołań
        sections_to_generate = [
            ("1. Kluczowe Punkty Wspólne", lambda: generate_kluczowe_punkty(all_articles_content_str, keyword)),
            ("2. Unikalne i Wyróżniające Się Elementy", lambda: generate_unikalne_elementy(all_articles_content_str, keyword)),
            ("3. Sugerowane Słowa Kluczowe i Semantyka", lambda: generate_słowa_kluczowe(all_articles_content_str, keyword)),
            ("4. Proponowana Struktura Artykułu (Szkic)", lambda: generate_struktura_artykulu(all_articles_content_str, keyword)),
            ("5. Sekcja FAQ (Pytania i Odpowiedzi)", lambda: generate_faq(all_articles_content_str, keyword)),
            ("6. Wskazówki SEO dla AI Overviews (SGE)", lambda: generate_wskazowki_sge(all_articles_content_str, keyword, ai_overview_text_from_serp))
        ]

        for i, (section_title, generation_func) in enumerate(sections_to_generate):
            st.write(f"Generowanie sekcji: {section_title}...")
            part = generation_func()
            report_parts.append(part)
            report_progress.progress((i + 1) / total_sections)
            time.sleep(0.5) # Małe opóźnienie, aby uniknąć zbyt szybkich wywołań API (opcjonalne)

        full_report = "\n\n".join(report_parts)
        report_progress.empty()

        if not full_report or all(p.startswith("###") and "Brak danych" in p or "Błąd generowania" in p for p in report_parts):
             st.error("Generowanie raportu przez Gemini nie powiodło się dla żadnej sekcji lub zwróciło błędy.")
             st.stop()

        st.info("Etap 4/4: Formatowanie wyników...")
        report_sections = parse_report(full_report)
        
        st.balloons()
        st.success("✅ Audyt SEO gotowy!")
        st.markdown(f"--- \n## Audyt SEO i plan treści dla frazy: '{keyword}'")

        # Wyświetlanie zakładek na podstawie wygenerowanych sekcji
        # Używamy `sections_to_generate` do ustalenia kolejności i nazw zakładek
        actual_tab_titles = []
        for section_title_tuple, _ in sections_to_generate:
            # Usuwamy numerację z początku tytułu dla nazwy zakładki, jeśli jest
            clean_title = re.sub(r"^\d+\.\s*", "", section_title_tuple)
            if clean_title in report_sections and report_sections[clean_title].strip():
                actual_tab_titles.append(clean_title)
        
        if actual_tab_titles:
            tabs = st.tabs(actual_tab_titles)
            for i, tab_title in enumerate(actual_tab_titles):
                with tabs[i]:
                    st.header(tab_title) # Używamy czystego tytułu
                    st.markdown(report_sections[tab_title]) # Pobieramy treść używając czystego tytułu
        else:
            st.warning("Brak danych do wyświetlenia w zakładkach.")
else:
    if keyword: st.info(f"Wprowadzono frazę: '{keyword}'. Kliknij przycisk powyżej, aby rozpocząć analizę.")
