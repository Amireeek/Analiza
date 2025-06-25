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
    # (bez zmian w tej funkcji w stosunku do poprzedniej pełnej wersji - usunięto tylko komentarze st.write)
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
                    if item.get("text"):
                        ai_overview_text_content = item.get("text")
                    elif item.get("description"):
                         ai_overview_text_content = item.get("description")
                    elif item.get("paragraphs") and isinstance(item.get("paragraphs"), list):
                        ai_overview_text_content = "\n\n".join([p.get("text", "") for p in item.get("paragraphs") if p.get("text")])
        else:
            status_message = data.get("status_message", "Nieznany błąd.")
            tasks_error = ""
            if data.get("tasks") and data["tasks"][0].get("status_message") != "Ok.":
                tasks_error = f" Błąd zadania: {data['tasks'][0]['status_code']} - {data['tasks'][0]['status_message']}"
            st.warning(f"DataForSEO API zwróciło nieoczekiwany status lub brak wyników: {status_message}{tasks_error}.")
        
        return {'organic_results': organic_results_list, 'ai_overview_text': ai_overview_text_content}

    except requests.exceptions.Timeout:
        st.error(f"🛑 Przekroczono czas oczekiwania na odpowiedź od DataForSEO dla zapytania: '{query}'")
    except requests.exceptions.RequestException as e:
        st.error(f"🛑 Błąd podczas komunikacji z API DataForSEO: {e}")
    except Exception as e:
        st.error(f"🛑 Nieoczekiwany błąd podczas przetwarzania odpowiedzi z DataForSEO: {e}")
    
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
        if not extracted_text:
             return None
        cleaned_text = re.sub(r'\s+', ' ', extracted_text).strip()
        return cleaned_text if len(cleaned_text) > 100 else None
    except requests.exceptions.RequestException as e:
        st.warning(f"⚠️ Nie udało się pobrać treści z {url_to_scrape} (ScrapingBee): {e}")
        return None
    except Exception as e:
        st.warning(f"⚠️ Wystąpił nieoczekiwany błąd podczas przetwarzania treści z {url_to_scrape}: {e}")
        return None


@st.cache_data(show_spinner="AI analizuje treść...")
def analyze_content_with_gemini(all_content, keyword_phrase, ai_overview_text=None):
    """Analizuje zagregowaną treść, AI Overview i generuje raport z Gemini."""
    if not all_content and not ai_overview_text:
        return "Brak treści (artykułów i AI Overview) do analizy przez AI."

    # --- ZMIANA TUTAJ: Bardziej bezpośrednie instrukcje dla sekcji AI Overview ---
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
W związku z tym, podaj 5-7 ogólnych, ale kluczowych i praktycznych wskazówek SEO, które pomagają twórcom treści zoptymalizować ich materiały tak, aby zwiększyć szansę na pojawienie się w AI Overviews (SGE) generowanych przez Google w przyszłości. Skup się na jakości, E-E-A-T, strukturze, bezpośrednich odpowiedziach i byciu pomocnym dla użytkownika.
"""

    prompt = f"""
Jesteś światowej klasy analitykiem SEO i strategiem content marketingu. Twoim zadaniem jest przeanalizowanie dostarczonej treści z czołowych artykułów dla frazy "{keyword_phrase}" oraz potencjalnie treści AI Overview. Na tej podstawie wygeneruj kompleksowy raport w formacie Markdown.

Raport musi być podzielony na DOKŁADNIE następujące sekcje, używając nagłówków `### numer. Nazwa sekcji` i **żadnych innych nagłówków H3 w tytułach sekcji raportu**:

### 1. Kluczowe Punkty Wspólne
(Wypunktuj tematy, podtematy, kluczowe informacje, perspektywy i style narracji, które powtarzają się w większości analizowanych tekstów z TOP10. Skup się na tym, co jest standardem i skonstruuj wytyczne dla copywritera)

### 2. Unikalne i Wyróżniające Się Elementy
(Wypunktuj nietypowe, oryginalne, innowacyjne lub szczególnie wartościowe informacje, dane, przykłady, case studies, infografiki (opisz co przedstawiają) lub perspektywy, które pojawiły się tylko w niektórych źródłach z TOP10 i mogą stanowić przewagę konkurencyjną dla nowego artykułu.)

### 3. Sugerowane Słowa Kluczowe i Semantyka
(Na podstawie analizy treści konkurencji z TOP10, stwórz listę 10-12 najważniejszych słów kluczowych, fraz długoogonowych i pojęć semantycznie powiązanych. Pogrupuj je tematycznie, jeśli to ułatwia zrozumienie. Wskaż intencję wyszukiwania dla frazy głównej.)

### 4. Proponowana Struktura Artykułu (Szkic)
(Zaproponuj idealną, rozbudowaną strukturę nowego artykułu w formacie Markdown, bazując na analizie TOP10. Użyj nagłówków drugiego poziomu (`##`) dla głównych sekcji i nagłówków trzeciego poziomu (`###`) dla podpunktów. **Zaproponuj DOKŁADNIE 3-4 główne sekcje (nagłówki H2) i dla każdej z nich przynajmniej 1-2 podpunkty (nagłówki H3) jako przykład hierarchii.** Uwzględnij kluczowe punkty, unikalne elementy i semantykę z analizy.)

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
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=8192, # Użyj maksymalnego dla flash lub trochę mniej dla bezpieczeństwa
        )
        response = model.generate_content(prompt, generation_config=generation_config)

        if hasattr(response, 'text') and response.text:
             return response.text
        else:
             st.warning("⚠️ Gemini zwróciło pustą odpowiedź lub błąd. Spróbuj ponownie lub zmień prompt.")
             if hasattr(response, 'prompt_feedback'): st.write("Feedback z promptu:", response.prompt_feedback)
             if hasattr(response, 'candidates') and response.candidates:
                  if response.candidates[0].finish_reason: st.write("Przyczyna zakończenia:", response.candidates[0].finish_reason)
                  if hasattr(response.candidates[0], 'safety_ratings'): st.write("Oceny bezpieczeństwa:", response.candidates[0].safety_ratings)
             return None
    except Exception as e:
        st.error(f"🛑 Błąd podczas komunikacji z Gemini API: {e}")
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
# (bez zmian w tej sekcji w stosunku do ostatniej pełnej wersji,
#  ale upewnij się, że logika zakładek poprawnie obsłuży jeden tytuł "Wskazówki SEO dla AI Overviews (SGE)")

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
        
        serp_data = get_serp_data_with_dataforseo(
            DATAFORSEO_LOGIN, 
            DATAFORSEO_PASSWORD, 
            keyword,
            num_results=10,
            location_code=2616,
            language_code='pl'
        )

        top_results = []
        ai_overview_text_from_serp = None

        if serp_data:
            top_results = serp_data.get('organic_results', [])
            ai_overview_text_from_serp = serp_data.get('ai_overview_text')
        
        if not top_results and ai_overview_text_from_serp is None:
            st.error("Nie udało się pobrać żadnych danych SERP (ani wyników organicznych, ani AI Overview) z DataForSEO. Audyt przerwany.")
            st.stop()
        if not top_results:
            st.warning(f"Nie znaleziono żadnych wyników organicznych TOP 10 dla frazy: '{keyword}' przy użyciu DataForSEO. Analiza będzie kontynuowana, jeśli znaleziono AI Overview.")

        BANNED_DOMAINS = [
            "youtube.com", "pinterest.", "instagram.com", "facebook.com",
            "olx.pl", "allegro.pl", "twitter.com", "tiktok.com",
            "wikipedia.org", "słownik.pl", "encyklopedia.", "forum.",
            ".gov", ".edu", "otodom.pl", "gratka.pl", "domiporta.pl"
        ]
        filtered_results = [r for r in top_results if r and r.get('link') and not any(b in r['link'].lower() for b in BANNED_DOMAINS)]

        if not filtered_results and not ai_overview_text_from_serp:
             st.error("Po filtracji nie pozostały żadne artykuły do analizy i nie znaleziono AI Overview.")
             st.stop()
        elif not filtered_results and ai_overview_text_from_serp:
             if ai_overview_text_from_serp:
                st.info("Nie znaleziono artykułów do analizy po filtracji, ale znaleziono AI Overview. Przechodzę do analizy AI.")
        elif filtered_results:
             if len(top_results) > len(filtered_results):
                  st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników organicznych (np. social media, sklepy), analizuję {len(filtered_results)} znalezionych artykułów.")
             st.subheader("Analizowane adresy URL (po filtracji):")
             for i, result in enumerate(filtered_results, 1):
                 display_title = result.get('title', result.get('link', f"Brak tytułu dla {result.get('link', 'nieznany URL')}"))
                 st.write(f"{i}. [{display_title}]({result.get('link', '#')})")

        all_articles_content_str = ""
        successful_sources_list = []
        if filtered_results:
            st.info("Etap 2/4: Pobieranie treści ze stron przez Scraping API (ScrapingBee)...")
            all_articles_content_list, successful_sources_list = [], []
            progress_bar = st.progress(0)
            for i, result in enumerate(filtered_results):
                url = result.get('link')
                if url:
                    content = scrape_and_clean_content(url, SCRAPINGBEE_API_KEY)
                    if content:
                        all_articles_content_list.append(content)
                        successful_sources_list.append({'title': result.get('title', 'Brak tytułu'), 'link': url})
                    progress_bar.progress((i + 1) / len(filtered_results))
            progress_bar.empty()

            if not all_articles_content_list:
                st.warning("Nie udało się pobrać treści z żadnej ze stron przy użyciu ScrapingBee. Analiza AI będzie bazować tylko na AI Overview (jeśli dostępne).")
            else:
                st.success(f"✅ Pomyślnie pobrano treści z {len(all_articles_content_list)} stron.")
                all_articles_content_str = "\n\n---\n\n".join(all_articles_content_list)
        
        if not all_articles_content_str and not ai_overview_text_from_serp:
            st.error("Brak treści artykułów oraz brak AI Overview do analizy. Audyt przerwany.")
            st.stop()

        st.info("Etap 3/4: Generowanie kompleksowego raportu przez AI (Gemini)...")
        full_report = analyze_content_with_gemini(all_articles_content_str, keyword, ai_overview_text_from_serp)

        if not full_report:
             st.error("Generowanie raportu przez Gemini nie powiodło się.")
             st.stop()

        st.info("Etap 4/4: Formatowanie wyników...")
        report_sections = parse_report(full_report)
        
        if successful_sources_list:
            sources_text = "\n".join([f"- [{source['title']}]({source['link']})" for source in successful_sources_list])
            report_sections["Analizowane Źródła Artykułów"] = "Poniżej lista adresów URL artykułów, których treść została pomyślnie pobrana i przeanalizowana przez AI:\n" + sources_text
        elif not filtered_results and ai_overview_text_from_serp:
            report_sections["Analizowane Źródła Artykułów"] = "Nie analizowano treści żadnych zewnętrznych artykułów (brak wyników po filtracji lub błąd pobierania). Analiza bazowała głównie na AI Overview."


        st.balloons()
        st.success("✅ Audyt SEO gotowy!")
        st.markdown(f"--- \n## Audyt SEO i plan treści dla frazy: '{keyword}'")

        # --- ZMIANA TUTAJ: Uproszczona logika zakładek dla AI Overview ---
        preferred_tab_order = [
            "Kluczowe Punkty Wspólne", "Unikalne i Wyróżniające Się Elementy",
            "Sugerowane Słowa Kluczowe i Semantyka", "Proponowana Struktura Artykułu (Szkic)",
            "Sekcja FAQ (Pytania i Odpowiedzi)",
            "Wskazówki SEO dla AI Overviews (SGE)", # Teraz tylko jeden możliwy tytuł
            "Analizowane Źródła Artykułów"
        ]
        
        actual_tab_titles = []
        for title in preferred_tab_order:
            if title in report_sections and report_sections[title].strip():
                 actual_tab_titles.append(title)
        
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
