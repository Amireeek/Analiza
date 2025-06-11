# app.py - Wersja PRO z kompletnym audytem SEO i zakładkami

import streamlit as st
import requests
import re
from trafilatura import extract
import google.generativeai as genai
from googleapiclient.discovery import build

# --- Konfiguracja strony ---
st.set_page_config(page_title="SEO Content Powerhouse", page_icon="🚀", layout="wide")
st.title("🚀 SEO Content Powerhouse z AI")
st.markdown("Narzędzie do tworzenia kompletnych strategii contentowych na podstawie analizy TOP 10 wyników Google.")

# --- Obsługa Kluczy API ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SEARCH_API_KEY = st.secrets["SEARCH_API_KEY"]
    SEARCH_ENGINE_ID = st.secrets["SEARCH_ENGINE_ID"]
    SCRAPINGBEE_API_KEY = st.secrets["SCRAPINGBEE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, FileNotFoundError):
    st.error("Błąd: Klucze API nie zostały znalezione. Upewnij się, że skonfigurowałeś WSZYSTKIE 4 sekrety w Streamlit.")
    st.stop()

# --- Funkcje Backendowe ---
@st.cache_data
def get_top_10_results(api_key, cse_id, query):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=query, cx=cse_id, num=10, gl='pl', hl='pl').execute()
    return res.get('items', [])

@st.cache_data
def scrape_and_clean_content(url_to_scrape):
    try:
        response = requests.get(
            url='https://app.scrapingbee.com/api/v1/',
            params={'api_key': SCRAPINGBEE_API_KEY, 'url': url_to_scrape, 'premium_proxy': 'true'},
            timeout=60
        )
        response.raise_for_status()
        return extract(response.text, include_comments=False, include_tables=False)
    except requests.exceptions.RequestException as e:
        st.warning(f"Nie udało się pobrać treści z {url_to_scrape}: {e}")
        return None

def analyze_content_with_gemini(all_content, keyword_phrase):
    if not all_content: return "Brak treści do analizy."
    
    # --- NOWY, KOMPLEKSOWY PROMPT ---
    prompt = f"""
    Jesteś światowej klasy analitykiem SEO i strategiem content marketingu. Przeanalizuj zagregowaną treść z czołowych artykułów dla frazy "{keyword_phrase}" i na tej podstawie wygeneruj kompleksowy raport w formacie Markdown. Raport musi być podzielony na DOKŁADNIE następujące sekcje, używając nagłówków `### numer. Nazwa sekcji`:

    ### 1. Kluczowe Punkty Wspólne
    (Wypunktuj tematy, które powtarzają się w większości tekstów.)

    ### 2. Unikalne i Wyróżniające Się Elementy
    (Wypunktuj ciekawe informacje, które pojawiły się tylko w niektórych źródłach.)

    ### 3. Sugerowane Słowa Kluczowe i Semantyka
    (Stwórz listę 15-20 najważniejszych słów kluczowych i fraz powiązanych. Pogrupuj je tematycznie, jeśli to ma sens.)

    ### 4. Proponowana Struktura Artykułu (Szkic)
    (Zaproponuj idealną strukturę nowego artykułu w formie nagłówków H2 i H3, od wstępu po podsumowanie.)

    ### 5. Sekcja FAQ (Pytania i Odpowiedzi)
    (Stwórz listę 4-5 najważniejszych pytań w stylu 'People Also Ask' i udziel na nie zwięzłych odpowiedzi.)

    ### 6. Wnioski i Rekomendacje
    (Stwórz listę praktycznych porad dla osoby, która chce napisać najlepszy artykuł na ten temat.)
    """
    
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(prompt)
    return response.text

# --- NOWA FUNKCJA DO PARSOWANIA RAPORTU ---
def parse_report(report_text):
    """Dzieli pełny raport na sekcje do wyświetlenia w zakładkach."""
    # Używamy wyrażeń regularnych do znalezienia treści pomiędzy nagłówkami
    sections = {}
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
            # Kroki 1 i 2: Pobieranie i filtrowanie
            st.write("Etap 1/4: Pobieranie i filtrowanie wyników z Google...")
            top_results = get_top_10_results(SEARCH_API_KEY, SEARCH_ENGINE_ID, keyword)
            if not top_results: st.error("Nie znaleziono wyników."); st.stop()
            
            BANNED_DOMAINS = ["youtube.com", "pinterest.", "instagram.com", "facebook.com", "olx.pl", "allegro.pl"]
            filtered_results = [r for r in top_results if not any(b in r.get('link','') for b in BANNED_DOMAINS)]
            
            if not filtered_results: st.error("Po filtracji nie pozostały żadne artykuły do analizy."); st.stop()
            st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników (wideo/social media), analizuję {len(filtered_results)} artykułów.")

            # Krok 3: Scraping
            st.write("Etap 2/4: Pobieranie treści ze stron przez Scraping API...")
            all_articles_content, successful_sources = [], []
            progress_bar = st.progress(0)
            for i, result in enumerate(filtered_results):
                content = scrape_and_clean_content(result.get('link'))
                if content:
                    all_articles_content.append(content)
                    successful_sources.append({'title': result.get('title'), 'link': result.get('link')})
                progress_bar.progress((i + 1) / len(filtered_results))

            if not all_articles_content: st.error("Nie udało się pobrać treści z żadnej ze stron."); st.stop()

            # Krok 4: Analiza AI
            st.write("Etap 3/4: Generowanie kompleksowego raportu przez AI...")
            aggregated_content = "\n\n---\n\n".join(all_articles_content)
            full_report = analyze_content_with_gemini(aggregated_content, keyword)
            
            st.write("Etap 4/4: Formatowanie wyników...")
            report_sections = parse_report(full_report)
            
            st.balloons()
            st.success("Audyt SEO gotowy!")
            
            st.markdown(f"--- \n## Audyt SEO i plan treści dla frazy: '{keyword}'")
            
            # --- NOWY INTERFEJS Z ZAKŁADKAMI ---
            tab_titles = [
                "Punkty Wspólne", "Unikalne Elementy", "Słowa Kluczowe",
                "Struktura Artykułu", "FAQ", "Rekomendacje"
            ]
            
            tabs = st.tabs([f"🔹 {title}" for title in tab_titles])

            with tabs[0]:
                st.markdown(report_sections.get("Kluczowe Punkty Wspólne", "Brak danych."))
            with tabs[1]:
                st.markdown(report_sections.get("Unikalne i Wyróżniające Się Elementy", "Brak danych."))
            with tabs[2]:
                st.markdown(report_sections.get("Sugerowane Słowa Kluczowe i Semantyka", "Brak danych."))
            with tabs[3]:
                st.markdown(report_sections.get("Proponowana Struktura Artykułu (Szkic)", "Brak danych."))
            with tabs[4]:
                st.markdown(report_sections.get("Sekcja FAQ (Pytania i Odpowiedzi)", "Brak danych."))
            with tabs[5]:
                st.markdown(report_sections.get("Wnioski i Rekomendacje", "Brak danych."))

            # Rozwijana lista ze źródłami na końcu
            with st.expander(f"Zobacz {len(successful_sources)} źródeł, które zostały pomyślnie przeanalizowane"):
                for source in successful_sources:
                    st.markdown(f"- **{source['title']}**\n  - [{source['link']}]({source['link']})")
    else:
        st.warning("Proszę wpisać frazę kluczową.")
