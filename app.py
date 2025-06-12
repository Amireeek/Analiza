# app.py - Wersja PRO z kompletnym audytem SEO i zakładkami

import streamlit as st
import requests
import re
from trafilatura import extract
import google.generativeai as genai
from googleapiclient.discovery import build
from concurrent.futures import ThreadPoolExecutor # Importujemy ThreadPoolExecutor

# --- Konfiguracja strony ---
st.set_page_config(page_title="SEO Content Powerhouse", page_icon="🚀", layout="wide")
st.title("🚀 SEO Content Powerhouse z AI")
st.markdown("Narzędzie do tworzenia kompletnych strategii contentowych na podstawie analizy TOP 10 wyników Google.")

# --- Obsługa Kluczy API ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SEARCH_API_KEY = st.secrets["SEARCH_API_KEY"]
    SEARCH_ENGINE_ID = st.secrets["SEARCH_ENGINE_ID"]
    SCRAPE_DO_API_KEY = st.secrets["SCRAPE_DO_API_KEY"] 
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, FileNotFoundError):
    st.error("Błąd: Klucze API nie zostały znalezione. Upewnij się, że skonfigurowałeś WSZYSTKIE 4 sekrety w Streamlit (w tym SCRAPE_DO_API_KEY).")
    st.stop()

# --- Funkcje Backendowe ---
@st.cache_data
def get_top_10_results(api_key, cse_id, query):
    """Pobiera 10 najlepszych wyników wyszukiwania Google dla danej frazy."""
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=query, cx=cse_id, num=10, gl='pl', hl='pl').execute()
    return res.get('items', [])

# Funkcja scrape_and_clean_content nie musi być już cachowana, bo będzie wywoływana w pętli równoległej
def scrape_and_clean_content(url_to_scrape, api_key_for_scrape_do):
    """
    Pobiera i czyści treść z podanego URL-a za pomocą scrape.do,
    zwracając ją w formacie Markdown.
    """
    try:
        response = requests.get(
            url=f'https://api.scrape.do/?token={api_key_for_scrape_do}&url={url_to_scrape}',
            timeout=60 # Ustaw timeout dla żądania HTTP do scrape.do
        )
        response.raise_for_status() # Sprawdź, czy żądanie zakończyło się sukcesem
        # Zmieniono output_format na 'markdown'
        return extract(response.text, include_comments=False, include_tables=False, output_format='markdown')
    except requests.exceptions.RequestException as e:
        st.warning(f"Nie udało się pobrać treści z {url_to_scrape} przy użyciu scrape.do: {e}")
        return None

def analyze_content_with_gemini(all_content, keyword_phrase):
    """
    Analizuje zagregowaną treść za pomocą Gemini AI i generuje kompleksowy raport SEO.
    """
    if not all_content: return "Brak treści do analizy."
    
    prompt = f"""
    Jesteś światowej klasy analitykiem SEO i strategiem content marketingu. Przeanalizuj zagregowaną treść z czołowych artykułów dla frazy "{keyword_phrase}". Twoim zadaniem jest stworzenie kompleksowego raportu SEO w formacie Markdown, który będzie stanowił wytyczne do stworzenia artykułu o najwyższej jakości i konkurencyjności w Google.

    Raport musi być podzielony na DOKŁADNIE następujące sekcje, używając nagłówków `### numer. Nazwa sekcji`. Każda sekcja musi być wypełniona szczegółowymi i praktycznymi informacjami.

    ### 1. Kluczowe Punkty Wspólne
    (Wypunktuj najważniejsze tematy, podtematy i zagadnienia, które powtarzają się w większości analizowanych tekstów z TOP 10. To są obligatoryjne elementy, które muszą znaleźć się w Twoim tekście, aby był on konkurencyjny i mógł pojawić się w TOP 10 na daną frazę.)

    ### 2. Unikalne i Wyróżniające Się Elementy
    (Wypunktuj ciekawe informacje, perspektywy, statystyki, przykłady lub elementy (np. infografiki, studia przypadków), które pojawiły się tylko w niektórych źródłach lub wyróżniają je spośród innych. Wskazówki, co może stanowić przewagę konkurencyjną.)

    ### 3. Sugerowane Słowa Kluczowe i Semantyka
    (Stwórz wyczerpującą listę 15-20 najważniejszych słów kluczowych i fraz kluczowych powiązanych (LSI keywords), które są kluczowe dla semantyki tematu. Pogrupuj je tematycznie, jeśli to ma sens, lub wskaż ich kontekst użycia. Te frazy powinny być naturalnie wplecione w treść.)

    ### 4. Proponowany Temat Wpisu i Struktura Artykułu (Szkic)
    (Zaproponuj **jeden konkretny, chwytliwy i zoptymalizowany pod SEO tytuł** dla nowego wpisu blogowego, który ma szansę przebić konkurencję. Następnie zaproponuj idealną, szczegółową strukturę tego artykułu w formie nagłówków. Struktura musi zawierać:
    **1. Nagłówek Wstępny (H2)**
    **2. Cztery (4) unikalne Nagłówki Główne (H2)**
    **3. Pod każdym z tych 4xH2, po jednym (1) unikalnym Nagłówku Podrzędnym (H3)**
    **4. Nagłówek Końcowy (H2) - Podsumowanie**

    Używaj następującego formatu Markdown dla struktury:
    ## Wstęp (H2)
    ## Pierwszy Nagłówek Główny (H2)
    ### Pierwszy Nagłówek Podrzędny (H3)
    ## Drugi Nagłówek Główny (H2)
    ### Drugi Nagłówek Podrzędny (H3)
    ## Trzeci Nagłówek Główny (H2)
    ### Trzeci Nagłówek Podrzędny (H3)
    ## Czwarty Nagłówek Główny (H2)
    ### Czwarty Nagłówek Podrzędny (H3)
    ## Podsumowanie (H2))

    ### 5. Sekcja FAQ (Pytania i Rozbudowane Odpowiedzi)
    (Stwórz listę 4-5 najważniejszych pytań w stylu 'People Also Ask' dla tej frazy kluczowej, które powinny znaleźć się w artykule. Dla każdego pytania **udziel szczegółowej, rozbudowanej, kilkuzdaniowej odpowiedzi**, bazując na całej przeanalizowanej treści. Odpowiedzi umieść bezpośrednio pod pytaniami.)

    ### 6. Wnioski i Rekomendacje
    (Stwórz listę praktycznych i konkretnych porad dla osoby, która chce napisać najlepszy artykuł na ten temat. Wskaż na co należy zwrócić uwagę, aby treść była wartościowa, angażująca i dobrze rankowała.)
    """
    
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    # Zwiększamy timeout dla odpowiedzi AI do 300 sekund (5 minut)
    # Jest to kluczowe przy dużych danych wejściowych i złożonych wymaganiach.
    response = model.generate_content(prompt, request_options={"timeout": 300}) 
    return response.text

# --- NOWA FUNKCJA DO PARSOWANIA RAPORTU ---
def parse_report(report_text):
    """Dzieli pełny raport na sekcje do wyświetlenia w zakładkach."""
    sections = {}
    # Używamy wyrażeń regularnych do znalezienia treści pomiędzy nagłówkami ### numer. Nazwa sekcji
    pattern = r"###\s*\d+\.\s*(.*?)\n(.*?)(?=\n###\s*\d+\.|$)"
    matches = re.findall(pattern, report_text, re.DOTALL)
    
    for match in matches:
        title = match[0].strip()
        content = match[1].strip()
        sections[title] = content
        
    return sections

# --- Interfejs Użytkownika ---
keyword = st.text_input("Wprowadź frazę kluczową, którą chcesz przeanalizować:", placeholder="np. jak dbać o buty skórzane")

if st.button("🚀 Wygeneruj Kompleksowy Audyt SEO"):
    if keyword:
        with st.spinner("Przeprowadzam pełny audyt... To może potrwać kilka minut."):
            st.write("Etap 1/4: Pobieranie i filtrowanie wyników z Google...")
            top_results = get_top_10_results(SEARCH_API_KEY, SEARCH_ENGINE_ID, keyword)
            if not top_results: st.error("Nie znaleziono wyników."); st.stop()
            
            # Domeny, które mają być pominięte w analizie treści (np. serwisy wideo, social media, sklepy)
            BANNED_DOMAINS = ["youtube.com", "pinterest.", "instagram.com", "facebook.com", "olx.pl", "allegro.pl"]
            filtered_results = [r for r in top_results if not any(b in r.get('link','') for b in BANNED_DOMAINS)]
            
            if not filtered_results: st.error("Po filtracji nie pozostały żadne artykuły do analizy. Zmień frazę kluczową lub dostosuj listę wykluczonych domen."); st.stop()
            st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników (wideo/social media/sklepy), analizuję {len(filtered_results)} artykułów.")

            st.write(f"Etap 2/4: Pobieranie treści ze stron przez scrape.do API (równolegle, max 5 wątków)...") 
            all_articles_content = []
            successful_sources = []
            
            progress_bar = st.progress(0)
            
            # Użycie ThreadPoolExecutor z maksymalnie 5 wątkami (zgodnie z limitem scrape.do)
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Tworzymy słownik, który mapuje obiekt Future (wynik zadania równoległego)
                # do oryginalnego obiektu 'result' (z linkiem i tytułem), aby łatwo odzyskać kontekst.
                future_to_result = {
                    executor.submit(scrape_and_clean_content, result.get('link'), SCRAPE_DO_API_KEY): result
                    for result in filtered_results
                }
                
                # Iterujemy po zakończonych zadaniach w miarę ich kończenia
                for i, future in enumerate(future_to_result):
                    result_item = future_to_result[future] # Pobieramy oryginalny obiekt result
                    content = future.result() # Pobieramy faktyczny wynik z funkcji (treść strony w Markdown)
                    
                    if content:
                        all_articles_content.append(content)
                        successful_sources.append({'title': result_item.get('title'), 'link': result_item.get('link')})
                    else:
                        st.warning(f"Nie udało się pobrać treści z: {result_item.get('link')}. Pominięto.")
                    
                    # Aktualizujemy pasek postępu (to działa sekwencyjnie, ale zadania w tle biegną)
                    progress_bar.progress((i + 1) / len(filtered_results))

            if not all_articles_content: st.error("Nie udało się pobrać treści z żadnej ze stron do analizy. Spróbuj ponownie lub zmień frazę."); st.stop()

            st.write("Etap 3/4: Generowanie kompleksowego raportu przez AI...")
            # Agregujemy całą, pełną treść (w formacie Markdown)
            aggregated_content = "\n\n---\n\n".join(all_articles_content)

            # Ostateczne sprawdzenie, czy agregacja nie jest pusta
            if not aggregated_content.strip():
                st.error("Nie pozostała żadna treść do analizy przez AI (po agregacji).")
                st.stop()

            full_report = analyze_content_with_gemini(aggregated_content, keyword)
            
            st.write("Etap 4/4: Formatowanie wyników...")
            report_sections = parse_report(full_report)
            
            st.balloons() # Animacja balony Streamlit
            st.success("Audyt SEO gotowy!")
            
            st.markdown(f"--- \n## Audyt SEO i plan treści dla frazy: '{keyword}'")
            
            # Definicja tytułów zakładek zgodna z nagłówkami w prompcie
            tab_titles = [
                "Punkty Wspólne",
                "Unikalne Elementy",
                "Słowa Kluczowe",
                "Struktura Artykułu",
                "FAQ",
                "Rekomendacje"
            ]
            
            # Tworzenie zakładek Streamlit
            tabs = st.tabs([f"🔹 {title}" for title in tab_titles])

            # Wyświetlanie treści w odpowiednich zakładkach
            with tabs[0]:
                st.markdown(report_sections.get("Kluczowe Punkty Wspólne", "Brak danych."))
            with tabs[1]:
                st.markdown(report_sections.get("Unikalne i Wyróżniające Się Elementy", "Brak danych."))
            with tabs[2]:
                st.markdown(report_sections.get("Sugerowane Słowa Kluczowe i Semantyka", "Brak danych."))
            with tabs[3]: 
                st.markdown(report_sections.get("Proponowany Temat Wpisu i Struktura Artykułu (Szkic)", "Brak danych."))
            with tabs[4]: 
                st.markdown(report_sections.get("Sekcja FAQ (Pytania i Rozbudowane Odpowiedzi)", "Brak danych."))
            with tabs[5]:
                st.markdown(report_sections.get("Wnioski i Rekomendacje", "Brak danych."))

            # Rozwijana lista ze źródłami na końcu
            with st.expander(f"Zobacz {len(successful_sources)} źródeł, które zostały pomyślnie przeanalizowane"):
                if successful_sources:
                    for source in successful_sources:
                        st.markdown(f"- **{source['title']}**\n  - [{source['link']}]({source['link']})")
                else:
                    st.markdown("Brak źródeł, z których udało się pobrać treść.")
    else:
        st.warning("Proszę wpisać frazę kluczową.")
