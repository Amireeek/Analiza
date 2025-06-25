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
import time

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
    """
    Pobiera TYLKO wyniki organiczne wyszukiwania Google używając API DataForSEO.
    Zwraca listę wyników organicznych.
    """
    post_data = [{"keyword": query, "location_code": location_code, "language_code": language_code, "depth": num_results}]
    headers = {'Content-Type': 'application/json'}
    endpoint_url = "https://api.dataforseo.com/v3/serp/google/organic/live/regular"
    organic_results_list = []
    try:
        response = requests.post(endpoint_url, auth=(login, password), headers=headers, json=post_data, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data.get("status_code") == 20000 and data.get("tasks") and data["tasks"][0].get("result") and data["tasks"][0]["result"][0].get("items"):
            items = data["tasks"][0]["result"][0]["items"]
            for item in items:
                item_type = item.get("type")
                if item_type == "organic": # Interesują nas tylko wyniki organiczne
                    title, link = item.get("title"), item.get("url")
                    if title and link: organic_results_list.append({'title': title, 'link': link})
        else:
            status_message = data.get("status_message", "Nieznany błąd.")
            tasks_error = ""
            if data.get("tasks") and data["tasks"][0].get("status_message") != "Ok.":
                tasks_error = f" Błąd zadania: {data['tasks'][0]['status_code']} - {data['tasks'][0]['status_message']}"
            st.warning(f"DataForSEO API zwróciło nieoczekiwany status lub brak wyników: {status_message}{tasks_error}.")
        return organic_results_list # Zwracamy tylko listę wyników organicznych
    except: # Uproszczona obsługa błędów
        return []


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

# --- Funkcje generujące KAŻDĄ SEKCJĘ RAPORTU ---
def generate_gemini_response(section_prompt, section_name):
    """Wysyła pojedynczy prompt do Gemini i zwraca odpowiedź."""
    # (bez zmian)
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
    # (bez zmian)
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 1. Kluczowe Punkty Wspólne".
Wypunktuj tematy, podtematy, kluczowe informacje, perspektywy i style narracji, które powtarzają się w większości analizowanych tekstów. Skup się na tym, co jest standardem i skonstruuj wytyczne dla copywritera. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 1. Kluczowe Punkty Wspólne`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "1. Kluczowe Punkty Wspólne")

def generate_unikalne_elementy(all_content, keyword_phrase):
    # (bez zmian)
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 2. Unikalne i Wyróżniające Się Elementy".
Wypunktuj nietypowe, oryginalne, innowacyjne lub szczególnie wartościowe informacje, dane, przykłady, case studies, infografiki (opisz co przedstawiają) lub perspektywy, które pojawiły się tylko w niektórych źródłach z TOP10 i mogą stanowić przewagę konkurencyjną dla nowego artykułu. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 2. Unikalne i Wyróżniające Się Elementy`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "2. Unikalne i Wyróżniające Się Elementy")

def generate_słowa_kluczowe(all_content, keyword_phrase):
    # (bez zmian)
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 3. Sugerowane Słowa Kluczowe i Semantyka".
Na podstawie analizy treści konkurencji z TOP10, stwórz listę 10-12 najważniejszych słów kluczowych, fraz długoogonowych i pojęć semantycznie powiązanych. Pogrupuj je tematycznie, jeśli to ułatwia zrozumienie. Wskaż intencję wyszukiwania dla frazy głównej. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 3. Sugerowane Słowa Kluczowe i Semantyka`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "3. Sugerowane Słowa Kluczowe i Semantyka")

def generate_struktura_artykulu(all_content, keyword_phrase):
    # --- ZMIANA TUTAJ: Jeszcze bardziej stanowcze instrukcje dotyczące struktury ---
    prompt = f"""Jako ekspert SEO specjalizujący się w tworzeniu BARDZO SZCZEGÓŁOWYCH i WYCZERPUJĄCYCH konspektów artykułów, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 4. Proponowana Struktura Artykułu (Szkic)".
Zaproponuj niezwykle rozbudowaną i dogłębną strukturę nowego artykułu w formacie Markdown. Struktura MUSI zawierać:
1.  Co najmniej 2-3 propozycje chwytliwych tytułów dla całego artykułu, odpowiednich dla frazy "{keyword_phrase}".
2.  Następnie, struktura MUSI być podzielona na **DOKŁADNIE 5 do 6 (pięć do sześciu) GŁÓWNYCH SEKCJI (każda jako nagłówek H2)**.
3.  Dla **KAŻDEJ z tych głównych sekcji H2, MUSISZ zaproponować **DOKŁADNIE 3 do 4 (trzy do czterech) bardziej szczegółowych podpunktów (każdy jako nagłówek H3)**.
Nagłówki H2 i H3 powinny być angażujące, precyzyjnie opisywać zawartość danego fragmentu i naturalnie zawierać słowa kluczowe, jeśli to możliwe. Dbaj o logiczny przepływ i kompleksowe pokrycie tematu, czerpiąc inspirację z analizy TOP10.
Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 4. Proponowana Struktura Artykułu (Szkic)`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "4. Proponowana Struktura Artykułu (Szkic)")

def generate_faq(all_content, keyword_phrase):
    # (bez zmian - instrukcja o odpowiedziach pod pytaniami już była)
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 5. Sekcja FAQ (Pytania i Odpowiedzi)".
Stwórz listę 4-5 najczęstszych pytań, na które odpowiadają konkurenci z TOP10, w stylu 'People Also Ask'. **Dla każdego pytania, podaj 2-3 zdaniową bezpośrednią odpowiedź, pisząc ją BEZPOŚREDNIO POD DANYM PYTANIEM, w nowej linii.** Użyj formatowania Markdown: pytanie jako zwykły tekst lub pogrubiony, a odpowiedź pod nim. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 5. Sekcja FAQ (Pytania i Odpowiedzi)`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "5. Sekcja FAQ (Pytania i Odpowiedzi)")

# Funkcja generate_wskazowki_sge nie jest już potrzebna, bo usuwamy tę sekcję

def parse_report(report_text):
    """Dzieli pełny raport na sekcje do wyświetlenia w zakładkach."""
    # (bez zmian)
    if not report_text: return {}
    sections = {}
    pattern = r"###\s*(?:\d+\.\s*)?(.*?)\n(.*?)(?=\n###\s*\d+\.|$|\Z)"
    matches = re.findall(pattern, report_text, re.DOTALL)
    for match in matches:
        title = match[0].strip()
        content = match[1].strip()
        if title and content:
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
        # --- ZMIANA TUTAJ: get_serp_data_with_dataforseo zwraca teraz tylko listę wyników organicznych ---
        top_results = get_serp_data_with_dataforseo(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD, keyword)
        
        if not top_results: # Jeśli nie ma żadnych wyników organicznych
            st.error(f"Nie udało się pobrać wyników organicznych z DataForSEO dla frazy '{keyword}'. Audyt przerwany.")
            st.stop()

        BANNED_DOMAINS = ["youtube.com", "pinterest.", "instagram.com", "facebook.com", "olx.pl", "allegro.pl", "twitter.com", "tiktok.com", "wikipedia.org", "słownik.pl", "encyklopedia.", "forum.", ".gov", ".edu", "otodom.pl", "gratka.pl", "domiporta.pl"]
        filtered_results = [r for r in top_results if r and r.get('link') and not any(b in r['link'].lower() for b in BANNED_DOMAINS)]

        if not filtered_results:
             st.error("Po filtracji nie pozostały żadne artykuły do analizy.")
             st.stop()
        
        if len(top_results) > len(filtered_results):
            st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników, analizuję {len(filtered_results)} artykułów.")
        st.subheader("Analizowane adresy URL (po filtracji):")
        for i, r in enumerate(filtered_results, 1): st.write(f"{i}. [{r.get('title', r.get('link'))}]({r.get('link', '#')})")

        all_articles_content_str = ""
        if filtered_results: # Tylko jeśli są artykuły do scrapowania
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
            if not all_articles_content_list: st.warning("Nie udało się pobrać treści z żadnej ze stron. Raport będzie bazował na dostępnych informacjach.")
            else:
                st.success(f"✅ Pomyślnie pobrano treści z {len(all_articles_content_list)} stron.")
                all_articles_content_str = "\n\n---\n\n".join(all_articles_content_list)
        
        if not all_articles_content_str and not filtered_results: # Jeśli nie ma ani treści, ani nawet linków (co nie powinno się zdarzyć jeśli filtered_results jest warunkiem)
            st.error("Brak treści artykułów do analizy. Audyt przerwany.")
            st.stop()

        st.info("Etap 3/4: Generowanie raportu przez AI (Gemini) - sekcja po sekcji...")
        report_parts = []
        report_progress = st.progress(0)
        
        # --- ZMIANA TUTAJ: Usunięto sekcję SGE z listy generowania ---
        sections_to_generate = [
            ("1. Kluczowe Punkty Wspólne", lambda: generate_kluczowe_punkty(all_articles_content_str, keyword)),
            ("2. Unikalne i Wyróżniające Się Elementy", lambda: generate_unikalne_elementy(all_articles_content_str, keyword)),
            ("3. Sugerowane Słowa Kluczowe i Semantyka", lambda: generate_słowa_kluczowe(all_articles_content_str, keyword)),
            ("4. Proponowana Struktura Artykułu (Szkic)", lambda: generate_struktura_artykulu(all_articles_content_str, keyword)),
            ("5. Sekcja FAQ (Pytania i Odpowiedzi)", lambda: generate_faq(all_articles_content_str, keyword))
        ]
        total_sections = len(sections_to_generate)

        for i, (section_title, generation_func) in enumerate(sections_to_generate):
            st.write(f"Generowanie sekcji: {section_title}...") # Daje feedback użytkownikowi
            part = generation_func()
            report_parts.append(part)
            report_progress.progress((i + 1) / total_sections)
            # time.sleep(0.5) # Można przywrócić, jeśli API Gemini ma problemy z rate limiting

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

        # --- ZMIANA TUTAJ: Usunięto sekcję SGE i Analizowane Źródła z zakładek ---
        preferred_tab_order = [
            "Kluczowe Punkty Wspólne", "Unikalne i Wyróżniające Się Elementy",
            "Sugerowane Słowa Kluczowe i Semantyka", "Proponowana Struktura Artykułu (Szkic)",
            "Sekcja FAQ (Pytania i Odpowiedzi)"
        ]
        
        actual_tab_titles = [title for title in preferred_tab_order if title in report_sections and report_sections[title].strip()]
        
        if actual_tab_titles:
            tabs = st.tabs(actual_tab_titles)
            for i, tab_title in enumerate(actual_tab_titles): # Zmieniono mapowanie, aby było prostsze
                with tabs[i]:
                    st.header(tab_title)
                    st.markdown(report_sections[tab_title])
        else:
            st.warning("Brak danych do wyświetlenia w zakładkach.")
else:
    if keyword: st.info(f"Wprowadzono frazę: '{keyword}'. Kliknij przycisk powyżej, aby rozpocząć analizę.")
