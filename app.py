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
    Pobiera wyniki wyszukiwania Google (organiczne i AI Overview) używając API DataForSEO.
    Zwraca słownik: {'organic_results': [], 'ai_overview_text': "tekst lub None"}
    """
    # (bez zmian w tej funkcji - usunięto tylko komentarze st.write)
    post_data = [{"keyword": query, "location_code": location_code, "language_code": language_code, "depth": num_results}]
    headers = {'Content-Type': 'application/json'}
    endpoint_url = "https://api.dataforseo.com/v3/serp/google/organic/live/regular"
    organic_results_list = []
    ai_overview_text_content = None
    try:
        response = requests.post(endpoint_url, auth=(login, password), headers=headers, json=post_data, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data.get("status_code") == 20000 and data.get("tasks") and data["tasks"][0].get("result") and data["tasks"][0]["result"][0].get("items"):
            items = data["tasks"][0]["result"][0]["items"]
            for item in items:
                item_type = item.get("type")
                if item_type == "organic":
                    title = item.get("title")
                    link = item.get("url")
                    if title and link:
                        organic_results_list.append({'title': title, 'link': link})
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
    except requests.exceptions.Timeout: st.error(f"🛑 Przekroczono czas oczekiwania na DataForSEO dla '{query}'")
    except requests.exceptions.RequestException as e: st.error(f"🛑 Błąd komunikacji z DataForSEO: {e}")
    except Exception as e: st.error(f"🛑 Nieoczekiwany błąd przetwarzania odpowiedzi z DataForSEO: {e}")
    return {'organic_results': [], 'ai_overview_text': None}

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

@st.cache_data(show_spinner="AI analizuje treść...")
def analyze_content_with_gemini(all_content, keyword_phrase, ai_overview_text=None):
    """Analizuje zagregowaną treść, AI Overview i generuje raport z Gemini."""
    if not all_content and not ai_overview_text:
        return "Brak treści (artykułów i AI Overview) do analizy przez AI."

    ai_overview_instructions = ""
    if ai_overview_text:
        ai_overview_instructions = f"""
Przeanalizuj poniższy tekst AI Overview wygenerowany przez Google dla frazy "{keyword_phrase}":
---
{ai_overview_text}
---
Na podstawie tej analizy oraz Twojej wiedzy o SEO, sformułuj 5-7 konkretnych, praktycznych wskazówek dla twórców treści. Wskazówki powinny wyjaśniać, jakie elementy w ich własnych treściach (np. bezpośrednie odpowiedzi, struktura, użyte sformułowania, dane, przykłady) mogłyby zwiększyć prawdopodobieństwo, że Google wykorzysta ich materiały do generowania podobnych AI Overviews. Skup się na tym, co można zrobić, aby treść była "SGE-friendly".
"""
    else:
        ai_overview_instructions = f"""
Dla frazy "{keyword_phrase}" nie znaleziono AI Overview w dostarczonych danych. 
Mimo to, na podstawie analizy treści z artykułów TOP10 (dostarczonych w sekcji "Treść z artykułów TOP10 do analizy"), zidentyfikuj cechy tych treści, które mogłyby być korzystne z punktu widzenia generowania AI Overviews (SGE) przez Google. Podaj 5-7 praktycznych wskazówek SEO, jak na podstawie tych najlepszych artykułów z TOP10 można tworzyć treści "SGE-friendly". Skup się na jakości, strukturze, bezpośrednich odpowiedziach, E-E-A-T i byciu pomocnym dla użytkownika, czerpiąc inspirację z analizowanych artykułów.
"""

    prompt = f"""
Jesteś światowej klasy analitykiem SEO i strategiem content marketingu, specjalizującym się w tworzeniu wyczerpujących i bardzo szczegółowych konspektów artykułów. Twoim zadaniem jest przeanalizowanie dostarczonej treści z czołowych artykułów dla frazy "{keyword_phrase}" oraz potencjalnie treści AI Overview. Na tej podstawie wygeneruj kompleksowy raport w formacie Markdown.

Raport MUSI być podzielony na DOKŁADNIE następujące sekcje, używając nagłówków `### numer. Nazwa sekcji` i **żadnych innych nagłówków H3 w tytułach sekcji raportu**:

### 1. Kluczowe Punkty Wspólne
(Wypunktuj tematy, podtematy, kluczowe informacje, perspektywy i style narracji, które powtarzają się w większości analizowanych tekstów z TOP10. Skup się na tym, co jest standardem i skonstruuj wytyczne dla copywritera)

### 2. Unikalne i Wyróżniające Się Elementy
(Wypunktuj nietypowe, oryginalne, innowacyjne lub szczególnie wartościowe informacje, dane, przykłady, case studies, infografiki (opisz co przedstawiają) lub perspektywy, które pojawiły się tylko w niektórych źródłach z TOP10 i mogą stanowić przewagę konkurencyjną dla nowego artykułu.)

### 3. Sugerowane Słowa Kluczowe i Semantyka
(Na podstawie analizy treści konkurencji z TOP10, stwórz listę 10-12 najważniejszych słów kluczowych, fraz długoogonowych i pojęć semantycznie powiązanych. Pogrupuj je tematycznie, jeśli to ułatwia zrozumienie. Wskaż intencję wyszukiwania dla frazy głównej.)

### 4. Proponowana Struktura Artykułu (Szkic)
(Zaproponuj BARDZO ROZBUDOWANĄ i SZCZEGÓŁOWĄ strukturę nowego artykułu w formacie Markdown, bazując na analizie TOP10. Struktura MUSI zawierać **DOKŁADNIE 5 (pięć) głównych sekcji (nagłówki H2)**. Dla **KAŻDEJ z tych pięciu głównych sekcji (H2) zaproponuj DOKŁADNIE 3 (trzy) bardziej szczegółowe podpunkty (nagłówki H3)**. Nagłówki powinny być angażujące i precyzyjnie opisywać zawartość danego fragmentu. Dbaj o logiczny przepływ i kompleksowe pokrycie tematu. Uwzględnij kluczowe punkty, unikalne elementy i semantykę z analizy. Przykładowy tytuł artykułu: [Zaproponuj 2-3 chwytliwe tytuły dla artykułu o frazie "{keyword_phrase}"])

### 5. Sekcja FAQ (Pytania i Odpowiedzi)
(Stwórz listę 4-5 najczęstszych pytań, na które odpowiadają konkurenci z TOP10, w stylu 'People Also Ask'. Podaj 2-3 zdaniowe bezpośrednie odpowiedzi na te pytania, bazując na analizowanej treści. Odpowiedzi napisz pod pytaniami)

### 6. Wskazówki SEO dla AI Overviews (SGE)
{ai_overview_instructions}

Pamiętaj, aby Twoja odpowiedź była TYLKO treścią raportu w formacie Markdown, bez żadnych dodatkowych wstępów czy podsumowań poza strukturą raportu. Cała odpowiedź musi być w języku polskim.
Treść z artykułów TOP10 do analizy (jeśli dostępna):
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        generation_config = genai.types.GenerationConfig(max_output_tokens=8192) # Maksymalny dla flash
        response = model.generate_content(prompt, generation_config=generation_config)
        if hasattr(response, 'text') and response.text: return response.text
        else:
             st.warning("⚠️ Gemini zwróciło pustą odpowiedź lub błąd.")
             if hasattr(response, 'prompt_feedback'): st.write("Feedback:", response.prompt_feedback)
             if hasattr(response, 'candidates') and response.candidates and response.candidates[0].finish_reason:
                 st.write("Przyczyna zakończenia:", response.candidates[0].finish_reason)
             return None
    except Exception as e:
        st.error(f"🛑 Błąd komunikacji z Gemini API: {e}")
        return None

def parse_report(report_text):
    """Dzieli pełny raport na sekcje do wyświetlenia w zakładkach."""
    # (bez zmian)
    if not report_text: return {}
    sections = {}
    pattern = r"###\s*(?:\d+\.\s*)?(.*?)\n(.*?)(?=\n###\s*|$|\Z)"
    matches = re.findall(pattern, report_text, re.DOTALL)
    for match in matches:
        title = match[0].strip()
        content = match[1].strip()
        if title: sections[title] = content
    return sections

# ==============================================================================
# Krok 5: Interfejs Użytkownika i główna logika
# ==============================================================================
# (bez zmian w tej sekcji)
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

        all_articles_content_str, successful_sources_list = "", []
        if filtered_results:
            st.info("Etap 2/4: Pobieranie treści ze stron (ScrapingBee)...")
            all_articles_content_list = []
            progress_bar = st.progress(0)
            for i, result in enumerate(filtered_results):
                url = result.get('link')
                if url:
                    content = scrape_and_clean_content(url, SCRAPINGBEE_API_KEY)
                    if content:
                        all_articles_content_list.append(content)
                        # successful_sources_list.append({'title': result.get('title', 'Brak tytułu'), 'link': url}) # Usunięto, bo zakładka źródeł jest usunięta
                    progress_bar.progress((i + 1) / len(filtered_results))
            progress_bar.empty()
            if not all_articles_content_list: st.warning("Nie udało się pobrać treści z żadnej ze stron.")
            else:
                st.success(f"✅ Pomyślnie pobrano treści z {len(all_articles_content_list)} stron.")
                all_articles_content_str = "\n\n---\n\n".join(all_articles_content_list)
        
        if not all_articles_content_str and not ai_overview_text_from_serp:
            st.error("Brak treści artykułów oraz brak AI Overview do analizy. Audyt przerwany.")
            st.stop()

        st.info("Etap 3/4: Generowanie raportu przez AI (Gemini)...")
        full_report = analyze_content_with_gemini(all_articles_content_str, keyword, ai_overview_text_from_serp)
        if not full_report:
             st.error("Generowanie raportu przez Gemini nie powiodło się.")
             st.stop()

        st.info("Etap 4/4: Formatowanie wyników...")
        report_sections = parse_report(full_report)
        
        st.balloons()
        st.success("✅ Audyt SEO gotowy!")
        st.markdown(f"--- \n## Audyt SEO i plan treści dla frazy: '{keyword}'")

        preferred_tab_order = [
            "Kluczowe Punkty Wspólne", "Unikalne i Wyróżniające Się Elementy",
            "Sugerowane Słowa Kluczowe i Semantyka", "Proponowana Struktura Artykułu (Szkic)",
            "Sekcja FAQ (Pytania i Odpowiedzi)",
            "Wskazówki SEO dla AI Overviews (SGE)"
        ]
        
        actual_tab_titles = [title for title in preferred_tab_order if title in report_sections and report_sections[title].strip()]
        
        if actual_tab_titles:
            tabs = st.tabs(actual_tab_titles)
            tab_title_map = {i: title for i, title in enumerate(actual_tab_titles)}
            for i in range(len(tabs)):
                with tabs[i]:
                    current_title = tab_title_map[i]
                    st.header(current_title)
                    st.markdown(report_sections[current_title])
        else:
            st.warning("Brak danych do wyświetlenia w zakładkach.")
else:
    if keyword: st.info(f"Wprowadzono frazę: '{keyword}'. Kliknij przycisk powyżej, aby rozpocząć analizę.")
