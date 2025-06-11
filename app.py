# app.py - wersja z ulepszonym scraperem

import streamlit as st
import httpx  # Używamy bardziej zaawansowanej biblioteki HTTP
from trafilatura import extract
import google.generativeai as genai
from googleapiclient.discovery import build

# --- Konfiguracja strony (bez zmian) ---
st.set_page_config(page_title="Analizator SERP z Gemini", page_icon="💡", layout="wide")
st.title("💡 Analizator SERP z AI")
st.markdown("Narzędzie do głębokiej analizy treści z TOP 10 wyników Google przy użyciu Gemini 1.5 Pro.")

# --- Obsługa Kluczy API (bez zmian) ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SEARCH_API_KEY = st.secrets["SEARCH_API_KEY"]
    SEARCH_ENGINE_ID = st.secrets["SEARCH_ENGINE_ID"]
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, FileNotFoundError):
    st.error("Błąd: Klucze API nie zostały znalezione. Upewnij się, że skonfigurowałeś sekrety w Streamlit.")
    st.stop()

# --- Funkcje Backendowe (Z AKTUALIZACJĄ) ---
@st.cache_data
def get_top_10_results(api_key, cse_id, query):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=query, cx=cse_id, num=10, gl='pl', hl='pl').execute()
    return res.get('items', [])

# --- ULEPSZONA FUNKCJA SCRAPINGU ---
@st.cache_data
def scrape_and_clean_content(url):
    # Nagłówki udające popularną przeglądarkę na systemie Windows
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/'
    }
    try:
        # Używamy httpx, który jest nowoczesnym klientem HTTP
        with httpx.Client(headers=headers, follow_redirects=True, timeout=15) as client:
            response = client.get(url)
            # Sprawdzamy, czy serwer nie zwrócił błędu (np. 403, 500)
            response.raise_for_status()
            # Jeśli wszystko jest OK, przekazujemy treść do trafilatura
            return extract(response.text, include_comments=False, include_tables=False)
    except httpx.HTTPStatusError as e:
        # Ten błąd łapie teraz 403 Forbidden i inne błędy HTTP
        st.warning(f"Nie udało się pobrać treści z {url} (Błąd HTTP: {e.response.status_code}). Strona prawdopodobnie blokuje boty.")
        return None
    except Exception as e:
        st.warning(f"Wystąpił inny błąd podczas próby pobrania treści z {url}: {e}")
        return None

# --- Pozostałe funkcje (bez zmian) ---
def analyze_content_with_gemini(all_content, keyword_phrase):
    if not all_content:
        return "Brak treści do analizy."
    
    prompt = f"""
    Jesteś analitykiem SEO i ekspertem od strategii content marketingu. Twoim zadaniem jest dogłębna analiza treści z najlepszych artykułów z polskiego Google dla frazy "{keyword_phrase}". Poniżej znajduje się zagregowana, oczyszczona treść tych artykułów.

    ---
    {all_content}
    ---

    Na podstawie powyższego materiału wykonaj następujące zadania:
    1.  **ZIDENTYFIKUJ KLUCZOWE PUNKTY WSPÓLNE:** Znajdź i wypunktuj tematy, zagadnienia i porady, które powtarzają się w większości artykułów.
    2.  **WSKAŻ UNIKALNE I WYRÓŻNIAJĄCE SIĘ ELEMENTY:** Wypunktuj ciekawe, nietypowe informacje lub perspektywy, które pojawiły się tylko w niektórych artykułach.
    3.  **SFORMUŁUJ WNIOSKI I REKOMENDACJE:** Stwórz listę praktycznych wniosków i rekomendacji dla osoby, która chce napisać najlepszy, najbardziej kompletny artykuł na ten temat.

    Sformatuj swoją odpowiedź używając Markdown (nagłówki, listy, pogrubienia) dla maksymalnej czytelności.
    """
    
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(prompt)
    return response.text

# --- Interfejs Użytkownika (bez zmian) ---
keyword = st.text_input(
    "Wprowadź frazę kluczową, którą chcesz przeanalizować:",
    placeholder="np. jak zacząć inwestować małe kwoty"
)

if st.button("🚀 Rozpocznij Analizę"):
    if keyword:
        with st.spinner("Trwa analiza... To może potrwać kilka minut. Proszę czekać."):
            st.write("Krok 1/3: Pobieranie listy TOP 10 wyników z Google...")
            top_results = get_top_10_results(SEARCH_API_KEY, SEARCH_ENGINE_ID, keyword)
            
            if not top_results:
                st.error("Nie znaleziono wyników dla tej frazy w Google.")
                st.stop()

            st.write("Krok 2/3: Pobieranie i czyszczenie treści z każdej strony...")
            all_articles_content = []
            progress_bar = st.progress(0)
            for i, result in enumerate(top_results):
                url = result.get('link')
                content = scrape_and_clean_content(url)
                if content:
                    all_articles_content.append(content)
                progress_bar.progress((i + 1) / len(top_results))

            if not all_articles_content:
                st.error("Nie udało się pobrać treści z żadnej ze stron. Spróbuj inną frazę.")
                st.stop()

            st.write("Krok 3/3: Przekazywanie treści do analizy przez AI... To ostatni i najdłuższy etap.")
            aggregated_content = "\n\n---\n\n".join(all_articles_content)
            analysis_report = analyze_content_with_gemini(aggregated_content, keyword)
            
            st.balloons()
            st.success("Analiza zakończona!")
            
            st.markdown("---")
            st.markdown(f"## 深度 Pełna Analiza SERP dla frazy: '{keyword}'")
            st.markdown(analysis_report)
    else:
        st.warning("Proszę wpisać frazę kluczową.")
