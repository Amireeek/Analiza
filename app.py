# -*- coding: utf-8 -*-

# ==============================================================================
# Krok 1: Import bibliotek
# ==============================================================================
import streamlit as st
import requests
import re
import time # <<< ZMIANA KRYTYCZNA: Importujemy bibliotekę time >>>
from trafilatura import extract
import google.generativeai as genai
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
    SEARCH_API_KEY = st.secrets["SEARCH_API_KEY"]
    SEARCH_ENGINE_ID = st.secrets["SEARCH_ENGINE_ID"]
    SCRAPINGBEE_API_KEY = st.secrets["SCRAPINGBEE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError as e:
    st.error(f"🛑 Błąd konfiguracji sekretów! Nie znaleziono wymaganego sekretu: {e}.")
    st.stop()

# ==============================================================================
# Krok 4: Funkcje Backendowe
# ==============================================================================

# <<< ZMIANA KRYTYCZNA: Dodajemy dodatkowy argument `_` do funkcji >>>
# Dzięki temu możemy przekazać unikalną wartość (np. czas), aby za każdym razem ominąć cache.
@st.cache_data
def get_top_10_results(api_key, cse_id, query, _=None):
    """Pobiera 10 najlepszych wyników wyszukiwania Google dla danej frazy."""
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(q=query, cx=cse_id, num=10, gl='pl', hl='pl').execute()
        if 'items' not in res or not res['items']:
            return []
        return [{'title': item.get('title'), 'link': item.get('link')} for item in res['items']]
    except Exception as e:
        st.error(f"🛑 Błąd podczas pobierania wyników z Google Search API: {e}")
        return None

@st.cache_data
def scrape_and_clean_content(url_to_scrape, scrapingbee_api_key):
    """Pobiera i czyści treść ze strony używając ScrapingBee."""
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
    except Exception as e:
        st.warning(f"⚠️ Nie udało się pobrać treści z {url_to_scrape}: {e}")
        return None

@st.cache_data(show_spinner="AI analizuje treść...")
def analyze_content_with_gemini(all_content, keyword_phrase):
    """Analizuje zagregowaną treść i generuje raport z Gemini."""
    if not all_content:
        return "Brak treści do analizy przez AI."

    # Ulepszony prompt
    prompt = f"""
Jesteś światowej klasy analitykiem SEO. Przeanalizuj treść z czołowych artykułów dla frazy "{keyword_phrase}" i wygeneruj kompleksowy raport w Markdown.

Twoja odpowiedź MUSI być podzielona na DOKŁADNIE 5 sekcji, używając nagłówków w formacie `### [Numer]. [Nazwa Sekcji]`.

### 1. Kluczowe Punkty Wspólne
Wypunktuj tematy i informacje, które powtarzają się w większości tekstów. To jest standard w TOP 10.

### 2. Unikalne i Wyróżniające Się Elementy
Wypunktuj oryginalne informacje, dane, przykłady, które mogą dać przewagę konkurencyjną.

### 3. Sugerowane Słowa Kluczowe i Semantyka
Stwórz listę 10-15 słów kluczowych i fraz. Określ intencję wyszukiwania.

### 4. Proponowana Struktura Artykułu (Szkic)
Stwórz ROZBUDOWANY plan artykułu. Twoja odpowiedź dla tej sekcji MUSI zawierać:
1.  Jeden chwytliwy tytuł (jako `# Tytuł Artykułu`).
2.  Krótki wstęp (2-3 zdania).
3.  Listę co najmniej 4-5 głównych sekcji (jako `## Nagłówek Sekcji`).
4.  Dla każdej sekcji H2, zaproponuj 2-4 podpunkty (jako `### Podpunkt`).

### 5. Sekcja FAQ (Pytania i Odpowiedzi)
Stwórz 4-5 pytań w stylu 'People Also Ask' z krótkimi odpowiedziami.

Pamiętaj, Twoja odpowiedź to TYLKO treść raportu w Markdown, po polsku.
Treść do analizy:
{all_content}
"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        return response.text if hasattr(response, 'text') else None
    except Exception as e:
        st.error(f"🛑 Błąd podczas komunikacji z Gemini API: {e}")
        return None

# Ulepszony parser
def parse_report(report_text):
    if not report_text: return {}
    sections = {}
    pattern = r"###\s*(\d+\.\s*.*?)\n(.*?)(?=\n###\s*\d+\.|$)"
    matches = re.findall(pattern, report_text, re.DOTALL | re.MULTILINE)
    for match in matches:
        title = match[0].strip()
        content = match[1].strip()
        if title:
            clean_title = re.sub(r"^\d+\.\s*", "", title)
            sections[clean_title] = content
    return sections

# ==============================================================================
# Krok 5: Interfejs Użytkownika Streamlit i główna logika
# ==============================================================================
keyword = st.text_input("Wprowadź frazę kluczową, którą chcesz przeanalizować:", placeholder="np. jak dbać o buty skórzane")

if st.button("🚀 Wygeneruj Kompleksowy Audyt SEO"):
    if not keyword:
        st.warning("Proszę wpisać frazę kluczową.")
        st.stop()

    with st.spinner("Przeprowadzam pełny audyt... To może potrwać kilka minut."):
        st.info("Etap 1/4: Pobieranie i filtrowanie wyników z Google...")
        
        # <<< ZMIANA KRYTYCZNA: Przekazujemy `time.time()` jako dodatkowy argument >>>
        # To powoduje, że Streamlit traktuje to wywołanie jako unikalne i nie używa starego cache'u.
        top_results = get_top_10_results(SEARCH_API_KEY, SEARCH_ENGINE_ID, keyword, _=time.time())

        if top_results is None:
            st.error("Wystąpił błąd podczas pobierania danych z Google. Sprawdź konfigurację API.")
            st.stop()
        if not top_results:
            st.error(f"Nie znaleziono żadnych wyników TOP 10 dla frazy: '{keyword}'. Sprawdź konfigurację SEARCH_ENGINE_ID w panelu Google - czy na pewno ma włączone 'Search the entire web'?")
            st.stop()

        BANNED_DOMAINS = ["youtube.com", "pinterest.", "instagram.com", "facebook.com", "olx.pl", "allegro.pl", "twitter.com", "tiktok.com", "wikipedia.org", ".gov", ".edu", "ceneo.pl", "skapiec.pl"]
        filtered_results = [r for r in top_results if r and r.get('link') and not any(b in r['link'].lower() for b in BANNED_DOMAINS)]

        if not filtered_results:
            st.error("Po filtracji nie pozostały żadne artykuły do analizy.")
            st.stop()

        if len(top_results) > len(filtered_results):
            st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników, analizuję {len(filtered_results)} znalezionych artykułów.")
        
        with st.expander("Zobacz analizowane adresy URL"):
            for i, result in enumerate(filtered_results, 1):
                st.write(f"{i}. [{result.get('title', 'Brak tytułu')}]({result.get('link', '#')})")

        st.info("Etap 2/4: Pobieranie treści ze stron...")
        all_articles_content, successful_sources = [], []
        progress_bar = st.progress(0, text="Pobieranie...")
        for i, result in enumerate(filtered_results):
             url = result.get('link')
             if url:
                 content = scrape_and_clean_content(url, SCRAPINGBEE_API_KEY)
                 if content:
                     all_articles_content.append(content)
                     successful_sources.append({'title': result.get('title', 'Brak tytułu'), 'link': url})
                 progress_bar.progress((i + 1) / len(filtered_results), text=f"Pobrano {i+1}/{len(filtered_results)}")
        progress_bar.empty()

        if not all_articles_content:
            st.error("Nie udało się pobrać treści z żadnej ze stron.")
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

        preferred_tab_order = ["Kluczowe Punkty Wspólne", "Unikalne i Wyróżniające Się Elementy", "Sugerowane Słowa Kluczowe i Semantyka", "Proponowana Struktura Artykułu (Szkic)", "Sekcja FAQ (Pytania i Odpowiedzi)", "Analizowane Źródła"]
        actual_tab_titles = [title for title in preferred_tab_order if title in report_sections and report_sections[title].strip()]

        if actual_tab_titles:
             tabs = st.tabs(actual_tab_titles)
             for i, tab in enumerate(tabs):
                 with tab:
                     current_title = actual_tab_titles[i]
                     st.header(current_title)
                     st.markdown(report_sections[current_title], unsafe_allow_html=True)
        else:
             st.warning("Brak danych do wyświetlenia. Odpowiedź z AI mogła być pusta lub w nieprawidłowym formacie.")
else:
    if keyword:
         st.info(f"Wprowadzono frazę: '{keyword}'. Kliknij przycisk powyżej, aby rozpocząć analizę.")
