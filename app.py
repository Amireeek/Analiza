# -*- coding: utf-8 -*-

# ==============================================================================
# Krok 0: Instalacja bibliotek
# ==============================================================================
# Jeśli uruchamiasz to lokalnie, upewnij się, że masz te biblioteki zainstalowane:
# pip install streamlit requests trafilatura google-generativeai google-api-python-client scrapingbee
# Jeśli uruchamiasz w Streamlit Cloud, dodaj je do pliku requirements.txt

# ==============================================================================
# Krok 1: Import bibliotek
# ==============================================================================
import streamlit as st
import requests
import re
from trafilatura import extract
import google.generativeai as genai
# googleapiclient.discovery nie będzie już potrzebne do pobierania SERP,
# ale zostawiam na wypadek innych potencjalnych zastosowań Google API
from googleapiclient.discovery import build


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
    # SEARCH_API_KEY i SEARCH_ENGINE_ID nie będą już używane do pobierania SERP,
    # ale mogą być przydatne, jeśli zdecydujesz się na inne funkcje Google API.
    # Jeśli są niepotrzebne, można je usunąć z secrets i z tego bloku.
    if "SEARCH_API_KEY" in st.secrets: # Opcjonalne ładowanie
        SEARCH_API_KEY = st.secrets["SEARCH_API_KEY"]
    if "SEARCH_ENGINE_ID" in st.secrets: # Opcjonalne ładowanie
        SEARCH_ENGINE_ID = st.secrets["SEARCH_ENGINE_ID"]
    SCRAPINGBEE_API_KEY = st.secrets["SCRAPINGBEE_API_KEY"]

    genai.configure(api_key=GEMINI_API_KEY)

except KeyError as e:
    missing_key = str(e).strip("'")
    if missing_key == "SCRAPINGBEE_API_KEY" or missing_key == "GEMINI_API_KEY":
        st.error(f"🛑 Błąd konfiguracji sekretów! Nie znaleziono wymaganego sekretu: {missing_key}. Upewnij się, że skonfigurowałeś przynajmniej GEMINI_API_KEY i SCRAPINGBEE_API_KEY w ustawieniach Streamlit.")
        st.stop()
    else:
        st.warning(f"Uwaga: Nie znaleziono opcjonalnego sekretu: {missing_key}. Jeśli nie planujesz używać funkcji z nim związanych, możesz to zignorować.")
except Exception as e:
    st.error(f"🛑 Wystąpił nieoczekiwany błąd podczas ładowania kluczy: {e}")
    st.stop()


# ==============================================================================
# Krok 4: Funkcje Backendowe
# ==============================================================================

@st.cache_data # Cache'owanie wyników wyszukiwania
def get_top_10_google_results_with_scrapingbee(api_key_sb, query, num_results=10, country_code='pl', language_code='pl'):
    """Pobiera wyniki wyszukiwania Google używając API ScrapingBee."""
    params = {
        'api_key': api_key_sb,
        'search': query,
        'nb_results': str(num_results),
        'country_code': country_code,
        'language': language_code, # Dodano parametr języka
        # Możesz dodać inne parametry zgodnie z dokumentacją ScrapingBee, np. 'device': 'desktop'
    }
    try:
        response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=60) # Zwiększony timeout
        response.raise_for_status() # Rzuci wyjątek dla błędów HTTP
        data = response.json()

        if 'organic_results' in data and data['organic_results']:
            results = []
            for item in data['organic_results']:
                # Sprawdzamy, czy klucze 'title' i 'link' istnieją
                title = item.get('title')
                link = item.get('link')
                if title and link:
                    results.append({'title': title, 'link': link})
                else:
                    st.warning(f"Pominięto wynik z ScrapingBee z powodu braku tytułu lub linku: {item}")
            return results
        else:
            st.warning(f"ScrapingBee nie zwróciło 'organic_results' dla zapytania: {query}. Odpowiedź: {data.get('error', data)}")
            return []

    except requests.exceptions.Timeout:
        st.error(f"🛑 Przekroczono czas oczekiwania na odpowiedź od ScrapingBee dla zapytania: {query}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"🛑 Błąd podczas komunikacji z API ScrapingBee: {e}")
        return None
    except Exception as e: # Ogólny wyjątek dla np. problemów z JSON
        st.error(f"🛑 Nieoczekiwany błąd podczas przetwarzania odpowiedzi z ScrapingBee: {e}")
        return None


@st.cache_data
def scrape_and_clean_content(url_to_scrape, scrapingbee_api_key):
    """Pobiera i czyści treść ze strony używając ScrapingBee (bez zmian)."""
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
def analyze_content_with_gemini(all_content, keyword_phrase):
    """Analizuje zagregowaną treść i generuje raport z Gemini (bez zmian)."""
    if not all_content:
        return "Brak treści do analizy przez AI."
    prompt = f"""
Jesteś światowej klasy analitykiem SEO i strategiem content marketingu. Twoim zadaniem jest przeanalizowanie dostarczonej treści z czołowych artykułów dla frazy "{keyword_phrase}" i na tej podstawie wygenerowanie kompleksowego raportu w formacie Markdown.

Raport musi być podzielony na DOKŁADNIE następujące sekcje, używając nagłówków `### numer. Nazwa sekcji` i **żadnych innych nagłówków H3 w tytułach sekcji raportu**:

### 1. Kluczowe Punkty Wspólne
(Wypunktuj tematy, podtematy, kluczowe informacje, perspektywy i style narracji, które powtarzają się w większości analizowanych tekstów. Skup się na tym, co jest standardem w TOP 10 i skonstruuj wytyczne dla copywritera)

### 2. Unikalne i Wyróżniające Się Elementy
(Wypunktuj nietypowe, oryginalne, innowacyjne lub szczególnie wartościowe informacje, dane, przykłady, case studies, infografiki (opisz co przedstawiają) lub perspektywy, które pojawiły się tylko w niektórych źródłach i mogą stanowić przewagę konkurencyjną dla nowego artykułu.)

### 3. Sugerowane Słowa Kluczowe i Semantyka
(Na podstawie analizy treści konkurencji, stwórz listę 10-12 najważniejszych słów kluczowych, fraz długoogonowych i pojęć semantycznie powiązanych. Pogrupuj je tematycznie, jeśli to ułatwia zrozumienie. Wskaż intencję wyszukiwania dla frazy głównej.)

### 4. Proponowana Struktura Artykułu (Szkic)
(Zaproponuj idealną, rozbudowaną strukturę nowego artykułu w formacie Markdown. Użyj nagłówków drugiego poziomu (`##`) dla głównych sekcji i nagłówków trzeciego poziomu (`###`) dla podpunktów. Zaproponuj kilka nagłówków do artykułu, zawierających **około 3 nagłówki H2 i 1 nagłówek H3 jako przykład hierarchii**. Uwzględnij kluczowe punkty, unikalne elementy i semantykę z analizy.)

### 5. Sekcja FAQ (Pytania i Odpowiedzi)
(Stwórz listę 4-5 najczęstszych pytań, na które odpowiadają konkurenci, w stylu 'People Also Ask'. Podaj 2-3 zdaniowe bezpośrednie odpowiedzi na te pytania, bazując na analizowanej treści. Odpowiedzi napisz pod pytaniami)


Pamiętaj, aby Twoja odpowiedź była TYLKO treścią raportu w formacie Markdown, bez żadnych dodatkowych wstępów czy podsumowań poza strukturą raportu. Cała odpowiedź musi być w języku polskim.
Treść do analizy:
{all_content}
"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
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
    """Dzieli pełny raport na sekcje do wyświetlenia w zakładkach (bez zmian)."""
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

keyword = st.text_input("Wprowadź frazę kluczową, którą chcesz przeanalizować:", placeholder="np. jak dbać o buty skórzane")

if st.button("🚀 Wygeneruj Kompleksowy Audyt SEO"):
    if not keyword:
        st.warning("Proszę wpisać frazę kluczową.")
        st.stop()

    if 'SCRAPINGBEE_API_KEY' not in st.secrets or 'GEMINI_API_KEY' not in st.secrets:
         st.error("Błąd: Klucze SCRAPINGBEE_API_KEY lub GEMINI_API_KEY nie są skonfigurowane w Streamlit Secrets.")
         st.stop()

    with st.spinner("Przeprowadzam pełny audyt... To może potrwać kilka minut."):
        st.info("Etap 1/4: Pobieranie i filtrowanie wyników z Google (przez ScrapingBee)...")
        
        # Używamy nowej funkcji z kluczem ScrapingBee
        top_results = get_top_10_google_results_with_scrapingbee(SCRAPINGBEE_API_KEY, keyword)

        if top_results is None: # Obsługa błędu krytycznego z API
            st.error("Wystąpił krytyczny błąd podczas pobierania wyników z ScrapingBee. Audyt przerwany.")
            st.stop()
        if not top_results:
            st.error(f"Nie znaleziono żadnych wyników TOP 10 dla frazy: '{keyword}' przy użyciu ScrapingBee. Spróbuj innej frazy.")
            st.stop()

        BANNED_DOMAINS = [
            "youtube.com", "pinterest.", "instagram.com", "facebook.com",
            "olx.pl", "allegro.pl", "twitter.com", "tiktok.com",
            "wikipedia.org", "słownik.pl", "encyklopedia.", "forum.",
            ".gov", ".edu", "otodom.pl", "gratka.pl", "domiporta.pl"
        ]
        filtered_results = [r for r in top_results if r and r.get('link') and not any(b in r['link'].lower() for b in BANNED_DOMAINS)]

        if not filtered_results:
            st.error("Po filtracji nie pozostały żadne artykuły do analizy.")
            st.stop()

        if len(top_results) > len(filtered_results):
             st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników, analizuję {len(filtered_results)} znalezionych artykułów.")

        st.subheader("Analizowane adresy URL (po filtracji):")
        for i, result in enumerate(filtered_results, 1):
            display_title = result.get('title', result.get('link', f"Brak tytułu dla {result.get('link', 'nieznany URL')}"))
            st.write(f"{i}. [{display_title}]({result.get('link', '#')})")

        st.info("Etap 2/4: Pobieranie treści ze stron przez Scraping API...")
        all_articles_content, successful_sources = [], []
        progress_bar = st.progress(0)
        for i, result in enumerate(filtered_results):
             url = result.get('link')
             if url:
                 content = scrape_and_clean_content(url, SCRAPINGBEE_API_KEY)
                 if content:
                     all_articles_content.append(content)
                     successful_sources.append({'title': result.get('title', 'Brak tytułu'), 'link': url})
                 progress_bar.progress((i + 1) / len(filtered_results))
        progress_bar.empty()

        if not all_articles_content:
            st.error("Nie udało się pobrać treści z żadnej ze stron. Sprawdź limity ScrapingBee lub dostępność stron.")
            st.stop()
        st.success(f"✅ Pomyślnie pobrano treści z {len(all_articles_content)} stron.")

        st.info("Etap 3/4: Generowanie kompleksowego raportu przez AI...")
        aggregated_content = "\n\n---\n\n".join(all_articles_content)
        full_report = analyze_content_with_gemini(aggregated_content, keyword)

        if not full_report:
             st.error("Generowanie raportu przez Gemini nie powiodło się.")
             st.stop()

        st.info("Etap 4/4: Formatowanie wyników...")
        report_sections = parse_report(full_report)
        sources_text = "\n".join([f"- [{source['title']}]({source['link']})" for source in successful_sources])
        report_sections["Analizowane Źródła"] = "Poniżej lista adresów URL, których treść została pomyślnie pobrana i przeanalizowana przez AI:\n" + sources_text

        st.balloons()
        st.success("✅ Audyt SEO gotowy!")
        st.markdown(f"--- \n## Audyt SEO i plan treści dla frazy: '{keyword}'")

        preferred_tab_order = [
            "Kluczowe Punkty Wspólne", "Unikalne i Wyróżniające Się Elementy",
            "Sugerowane Słowa Kluczowe i Semantyka", "Proponowana Struktura Artykułu (Szkic)",
            "Sekcja FAQ (Pytania i Odpowiedzi)", "Wnioski i Rekomendacje", "Analizowane Źródła"
        ]
        actual_tab_titles = [title for title in preferred_tab_order if title in report_sections and report_sections[title].strip()]
        if actual_tab_titles:
             sources_tab_title = "Analizowane Źródła"
             if sources_tab_title in actual_tab_titles: actual_tab_titles.remove(sources_tab_title)
             tabs_to_create = actual_tab_titles
             if sources_tab_title in report_sections and report_sections[sources_tab_title].strip():
                 tabs_to_create = actual_tab_titles + [sources_tab_title]
             if tabs_to_create:
                tabs = st.tabs(tabs_to_create)
                tab_title_map = {i: title for i, title in enumerate(tabs_to_create)}
                for i in range(len(tabs)):
                    with tabs[i]:
                        current_title = tab_title_map[i]
                        st.header(current_title)
                        st.markdown(report_sections[current_title])
             else: st.warning("Brak danych do wyświetlenia w zakładkach po przetworzeniu.")
        else: st.warning("Brak danych do wyświetlenia w zakładkach.")
else:
    if keyword: st.info(f"Wprowadzono frazę: '{keyword}'. Kliknij przycisk powyżej, aby rozpocząć analizę.")
