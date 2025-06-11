# app.py - wersja z profesjonalnym Scraping API (ScrapingBee)

import streamlit as st
import requests  # Wracamy do requests, bo jest prostsze do tego API
from trafilatura import extract
import google.generativeai as genai
from googleapiclient.discovery import build

# --- Konfiguracja strony (bez zmian) ---
st.set_page_config(page_title="Analizator SERP z Gemini", page_icon="💡", layout="wide")
st.title("💡 Analizator SERP z AI")
st.markdown("Narzędzie do głębokiej analizy treści z TOP 10 wyników Google przy użyciu Gemini 1.5 Pro.")

# --- Obsługa Kluczy API (Z DODATKOWYM KLUCZEM) ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SEARCH_API_KEY = st.secrets["SEARCH_API_KEY"]
    SEARCH_ENGINE_ID = st.secrets["SEARCH_ENGINE_ID"]
    # NOWY KLUCZ
    SCRAPINGBEE_API_KEY = st.secrets["SCRAPINGBEE_API_KEY"]
    
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, FileNotFoundError):
    st.error("Błąd: Klucze API nie zostały znalezione. Upewnij się, że skonfigurowałeś WSZYSTKIE 4 sekrety w Streamlit (w tym SCRAPINGBEE_API_KEY).")
    st.stop()

# --- Funkcje Backendowe (Z AKTUALIZACJĄ OSTATECZNĄ) ---
@st.cache_data
def get_top_10_results(api_key, cse_id, query):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=query, cx=cse_id, num=10, gl='pl', hl='pl').execute()
    return res.get('items', [])

# --- OSTATECZNA WERSJA FUNKCJI SCRAPINGU Z UŻYCIEM SCRAPINGBEE ---
@st.cache_data
def scrape_and_clean_content(url_to_scrape):
    try:
        # Budujemy zapytanie do API ScrapingBee
        response = requests.get(
            url='https://app.scrapingbee.com/api/v1/',
            params={
                'api_key': SCRAPINGBEE_API_KEY,
                'url': url_to_scrape,
                'render_js': 'false',  # Ustaw na 'true' jeśli strona wymaga JS, ale zużywa więcej kredytów
                'premium_proxy': 'true', # Używa lepszych, rezydencjalnych proxy
            },
            timeout=60  # Dajemy więcej czasu, bo proces jest bardziej złożony
        )
        # Sprawdzamy, czy samo API ScrapingBee nie zwróciło błędu
        response.raise_for_status()
        
        # Jeśli wszystko jest OK, przekazujemy zwróconą treść HTML do trafilatura
        return extract(response.text, include_comments=False, include_tables=False)
        
    except requests.exceptions.RequestException as e:
        st.warning(f"Nie udało się pobrać treści z {url_to_scrape} przez ScrapingBee: {e}")
        return None
    except Exception as e:
        st.warning(f"Wystąpił inny błąd podczas przetwarzania {url_to_scrape}: {e}")
        return None

# --- Pozostałe funkcje (bez zmian) ---
def analyze_content_with_gemini(all_content, keyword_phrase):
    if not all_content: return "Brak treści do analizy."
    
    prompt = f"""
    Jesteś ekspertem SEO i analitykiem content marketingu. Przeanalizuj zagregowaną treść z czołowych artykułów dla frazy "{keyword_phrase}" i na tej podstawie:
    1.  **Zidentyfikuj kluczowe punkty wspólne:** Wypunktuj tematy, które powtarzają się w większości tekstów.
    2.  **Wskaż unikalne elementy:** Wypunktuj ciekawe informacje, które pojawiły się tylko w niektórych źródłach.
    3.  **Sformułuj wnioski i rekomendacje:** Stwórz listę praktycznych porad dla kogoś, kto chce napisać najlepszy artykuł na ten temat.
    Sformatuj odpowiedź używając czytelnego Markdown.
    """
    
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(prompt)
    return response.text

# --- Interfejs Użytkownika (bez zmian) ---
keyword = st.text_input("Wprowadź frazę kluczową, którą chcesz przeanalizować:", placeholder="np. jak łączyć ubrania w zestawy")

if st.button("🚀 Rozpocznij Analizę"):
    if keyword:
        with st.spinner("Trwa analiza... Używamy zaawansowanych technik, to może potrwać kilka minut."):
            st.write("Krok 1/3: Pobieranie listy TOP 10 wyników z Google...")
            top_results = get_top_10_results(SEARCH_API_KEY, SEARCH_ENGINE_ID, keyword)
            if not top_results: st.error("Nie znaleziono wyników dla tej frazy."); st.stop()

            st.write("Krok 2/3: Pobieranie treści przez Scraping API (omijanie zabezpieczeń)...")
            all_articles_content = []
            progress_bar = st.progress(0)
            for i, result in enumerate(top_results):
                url = result.get('link')
                content = scrape_and_clean_content(url)
                if content: all_articles_content.append(content)
                progress_bar.progress((i + 1) / len(top_results))

            if not all_articles_content: st.error("Nie udało się pobrać treści z żadnej ze stron, nawet przy użyciu zaawansowanych technik."); st.stop()

            st.write("Krok 3/3: Przekazywanie treści do analizy przez AI...")
            aggregated_content = "\n\n---\n\n".join(all_articles_content)
            analysis_report = analyze_content_with_gemini(aggregated_content, keyword)
            
            st.balloons()
            st.success("Analiza zakończona!")
            st.markdown(f"--- \n## 深度 Pełna Analiza SERP dla frazy: '{keyword}'")
            st.markdown(analysis_report)
    else:
        st.warning("Proszę wpisać frazę kluczową.")
