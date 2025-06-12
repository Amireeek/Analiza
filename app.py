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
from trafilatura import extract # Upewnij się, że masz tę bibliotekę
import google.generativeai as genai
from googleapiclient.discovery import build # Upewnij się, że masz tę bibliotekę


# ==============================================================================
# Krok 2: Konfiguracja strony Streamlit
# ==============================================================================
st.set_page_config(page_title="SEO Content Powerhouse", page_icon="🚀", layout="wide")
st.title("🚀 SEO Content Powerhouse z AI")
st.markdown("Narzędzie do tworzenia kompletnych strategii contentowych na podstawie analizy TOP 10 wyników Google.")


# ==============================================================================
# Krok 3: Obsługa Kluczy API ze Streamlit Secrets
# ==============================================================================
# WAŻNE: Upewnij się, że skonfigurowałeś WSZYSTKIE 4 klucze jako sekrety w Streamlit
try:
    # Ręcznie wpisz te linie, aby uniknąć problemów z niewidocznymi znakami!
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SEARCH_API_KEY = st.secrets["SEARCH_API_KEY"]
    SEARCH_ENGINE_ID = st.secrets["SEARCH_ENGINE_ID"]
    SCRAPINGBEE_API_KEY = st.secrets["SCRAPINGBEE_API_KEY"] # Klucz ScrapingBee

    genai.configure(api_key=GEMINI_API_KEY)
    # Nie konfigurujemy od razu Google Search API, bo 'build' jest używane w funkcji

    #st.success("✅ Klucze API załadowane pomyślnie.") # Można odkomentować dla debugowania

except KeyError as e:
    st.error(f"🛑 Błąd konfiguracji sekretów! Nie znaleziono wymaganego sekretu: {e}. Upewnij się, że skonfigurowałeś WSZYSTKIE 4 sekrety (GEMINI_API_KEY, SEARCH_API_KEY, SEARCH_ENGINE_ID, SCRAPINGBEE_API_KEY) w ustawieniach Streamlit.")
    st.stop() # Zatrzymaj działanie aplikacji, jeśli klucze nie są skonfigurowane
except Exception as e:
    st.error(f"🛑 Wystąpił nieoczekiwany błąd podczas ładowania kluczy: {e}")
    st.stop()


# ==============================================================================
# Krok 4: Funkcje Backendowe
# ==============================================================================

@st.cache_data # Cache'owanie wyników wyszukiwania Google
def get_top_10_results(api_key, cse_id, query):
    """Pobiera 10 najlepszych wyników wyszukiwania Google dla danej frazy."""
    try:
        # Używamy wersji developera, która wymaga klucza API
        service = build("customsearch", "v1", developerKey=api_key)
        # num=10 ogranicza wyniki do 10, gl/hl=pl ustawia region i język na polski
        res = service.cse().list(q=query, cx=cse_id, num=10, gl='pl', hl='pl').execute()

        if 'items' not in res or not res['items']:
            # st.warning("Nie znaleziono żadnych wyników dla tej frazy.") # Komunikat będzie niżej w UI
            return []

        # Zwracamy listę słowników z tytułem i linkiem
        return [{'title': item.get('title'), 'link': item.get('link')} for item in res['items']]
    except Exception as e:
        st.error(f"🛑 Błąd podczas pobierania wyników z Google Search API: {e}")
        # st.info("Upewnij się, że Twój SEARCH_API_KEY jest poprawny i włączyłeś Custom Search API w Google Cloud.") # Można dodać więcej wskazówek
        return None # Zwróć None w przypadku błędu, aby go obsłużyć dalej


@st.cache_data # Cache'owanie pobranej treści
def scrape_and_clean_content(url_to_scrape, scrapingbee_api_key):
    """Pobiera i czyści treść ze strony używając ScrapingBee."""
    try:
        response = requests.get(
            url='https://app.scrapingbee.com/api/v1/',
            params={'api_key': scrapingbee_api_key, 'url': url_to_scrape, 'premium_proxy': 'true', 'block_resources': 'false'}, # Dodano block_resources
            timeout=90 # Zwiększono timeout na wypadek wolnych stron
        )
        response.raise_for_status() # Rzuca wyjątek dla kodów błędów HTTP (4xx, 5xx)

        # Używamy trafilatury do ekstrakcji czystego tekstu artykułu
        # Upewnij się, że treść response.text jest odpowiednia (np. zakodowana w UTF-8)
        extracted_text = extract(response.text, include_comments=False, include_tables=False, include_images=False) # Wyłączono obrazy

        if not extracted_text:
             #st.warning(f"Trafilatura nie zwróciła treści dla {url_to_scrape}") # Debug
             return None

        # Opcjonalnie: dodatkowe czyszczenie tekstu (np. usunięcie nadmiernych białych znaków)
        cleaned_text = re.sub(r'\s+', ' ', extracted_text).strip()

        return cleaned_text if len(cleaned_text) > 100 else None # Zwróć None jeśli treść jest za krótka

    except requests.exceptions.RequestException as e:
        st.warning(f"⚠️ Nie udało się pobrać treści z {url_to_scrape} (ScrapingBee): {e}")
        return None
    except Exception as e:
        st.warning(f"⚠️ Wystąpił nieoczekiwany błąd podczas przetwarzania treści z {url_to_scrape}: {e}")
        return None


@st.cache_data(show_spinner="AI analizuje treść...") # Cache'owanie wyników Gemini z innym spinnerem
def analyze_content_with_gemini(all_content, keyword_phrase):
    """Analizuje zagregowaną treść i generuje raport z Gemini."""
    if not all_content:
        return "Brak treści do analizy przez AI."

    # Wersja promptu zgodna z Twoim kodem
    prompt = f"""
Jesteś światowej klasy analitykiem SEO i strategiem content marketingu. Twoim zadaniem jest przeanalizowanie dostarczonej treści z czołowych artykułów dla frazy "{keyword_phrase}" i na tej podstawie wygenerowanie kompleksowego raportu w formacie Markdown.

Raport musi być podzielony na DOKŁADNIE następujące sekcje, używając nagłówków `### numer. Nazwa sekcji` i **żadnych innych nagłówków H3 w tytułach sekcji**:

### 1. Kluczowe Punkty Wspólne
(Wypunktuj tematy, podtematy, kluczowe informacje, perspektywy i style narracji, które powtarzają się w większości analizowanych tekstów. Skup się na tym, co jest standardem w TOP 10.)

### 2. Unikalne i Wyróżniające Się Elementy
(Wypunktuj nietypowe, oryginalne, innowacyjne lub szczególnie wartościowe informacje, dane, przykłady, case studies, infografiki (opisz co przedstawiają) lub perspektywy, które pojawiły się tylko w niektórych źródłach i mogą stanowić przewagę konkurencyjną dla nowego artykułu.)

### 3. Sugerowane Słowa Kluczowe i Semantyka
(Na podstawie analizy treści konkurencji, stwórz listę 15-20 najważniejszych słów kluczowych, fraz długoogonowych i pojęć semantycznie powiązanych. Pogrupuj je tematycznie, jeśli to ułatwia zrozumienie. Wskaż intencję wyszukiwania dla frazy głównej.)

### 4. Proponowana Struktura Artykułu (Szkic)
(Zaproponuj idealną, rozbudowaną strukturę nowego artykułu, która uwzględni kluczowe punkty, unikalne elementy i semantykę. Użyj hierarchii nagłówków H2 i H3. Pamiętaj o wstępie, rozwinięciu i podsumowaniu.)

### 5. Sekcja FAQ (Pytania i Odpowiedzi)
(Stwórz listę 4-5 najczęstszych pytań, na które odpowiadają konkurenci, w stylu 'People Also Ask'. Podaj zwięzłe, bezpośrednie odpowiedzi na te pytania, bazując na analizowanej treści.)

### 6. Wnioski i Rekomendacje
(Stwórz listę praktycznych porad i kluczowych wniosków dla autora, który ma napisać najlepszy możliwy artykuł na ten temat. Co powinien zrobić, aby przewyższyć konkurencję?)

### 7. Analizowane Źródła
(Wypisz listę URL-i, które zostały pomyślnie przeanalizowane.)

Pamiętaj, aby Twoja odpowiedź była TYLKO treścią raportu w formacie Markdown, bez żadnych dodatkowych wstępów czy podsumowań poza strukturą raportu. Cała odpowiedź musi być w języku polskim.
Treść do analizy:
{all_content}
"""

    try:
        # Używamy modelu gemini-1.5-flash-latest dla szybkości i kosztów
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)

        # Sprawdzenie, czy odpowiedź zawiera treść
        if hasattr(response, 'text') and response.text:
             return response.text
        else:
             st.warning("⚠️ Gemini zwróciło pustą odpowiedź lub błąd. Spróbuj ponownie lub zmień prompt.")
             if hasattr(response, 'prompt_feedback'):
                 st.write("Feedback z promptu:", response.prompt_feedback)
             if hasattr(response, 'candidates') and response.candidates:
                  st.write("Kandydaci:", response.candidates[0].finish_reason)
             return None


    except Exception as e:
        st.error(f"🛑 Błąd podczas komunikacji z Gemini API: {e}")
        # st.info("Upewnij się, że Twój GEMINI_API_KEY jest poprawny i masz dostęp do modelu 'gemini-1.5-flash-latest'.") # Wskazówka
        return None


# --- Funkcja do parsowania raportu (bez zmian) ---
def parse_report(report_text):
    """Dzieli pełny raport na sekcje do wyświetlenia w zakładkach."""
    if not report_text: return {}
    sections = {}
    # Poprawione wyrażenie regularne, aby poprawnie łapać sekcje (uwzględniając nową sekcję 7)
    pattern = r"###\s*(\d+)\.\s*(.*?)\n(.*?)(?=\n###\s*\d+\.|$)"
    matches = re.findall(pattern, report_text, re.DOTALL)

    for match in matches:
        section_number = match[0]
        title = match[1].strip()
        content = match[2].strip()
        sections[title] = content

    return sections


# ==============================================================================
# Krok 5: Interfejs Użytkownika Streamlit i główna logika
# ==============================================================================

# Pole formularza do wprowadzenia frazy
keyword = st.text_input("Wprowadź frazę kluczową, którą chcesz przeanalizować:", placeholder="np. jak dbać o buty skórzane")

# Przycisk do uruchomienia analizy
if st.button("🚀 Wygeneruj Kompleksowy Audyt SEO"):
    if not keyword:
        st.warning("Proszę wpisać frazę kluczową.")
        st.stop()

    # Sprawdzenie, czy klucze są dostępne przed rozpoczęciem
    # Ta logika została już częściowo obsłużona przez blok try/except na górze
    # ale warto dodać dodatkowe sprawdzenie, jeśli st.stop() było pominięte
    if 'GEMINI_API_KEY' not in st.secrets or 'SEARCH_API_KEY' not in st.secrets or 'SEARCH_ENGINE_ID' not in st.secrets or 'SCRAPINGBEE_API_KEY' not in st.secrets:
         st.error("Błąd: Nie wszystkie klucze API są skonfigurowane w Streamlit Secrets.")
         st.stop()


    with st.spinner("Przeprowadzam pełny audyt... To może potrwać kilka minut."):

        # Etap 1: Pobieranie wyników z Google
        st.info("Etap 1/4: Pobieranie i filtrowanie wyników z Google...")
        top_results = get_top_10_results(SEARCH_API_KEY, SEARCH_ENGINE_ID, keyword)

        if not top_results:
            st.error(f"Nie znaleziono żadnych wyników TOP 10 dla frazy: '{keyword}'.")
            st.stop()

        # Filtrowanie wyników (jak w Twoim kodzie)
        BANNED_DOMAINS = ["youtube.com", "pinterest.", "instagram.com", "facebook.com", "olx.pl", "allegro.pl", "twitter.com"] # Dodano twitter
        filtered_results = [r for r in top_results if r and r.get('link') and not any(b in r['link'] for b in BANNED_DOMAINS)] # Dodano sprawdzanie czy link istnieje i czy r nie jest None

        if not filtered_results:
            st.error("Po filtracji nie pozostały żadne artykuły do analizy (usunięto strony wideo, social media, sklepy, itp.).")
            st.stop()

        # Informacja o filtracji
        if len(top_results) > len(filtered_results):
             st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników (wideo/social media/sklepy), analizuję {len(filtered_results)} znalezionych artykułów.")

        st.subheader("Analizowane adresy URL:")
        for i, result in enumerate(filtered_results, 1):
            st.write(f"{i}. [{result.get('title', 'Brak tytułu')}]({result.get('link', '#')})")


        # Etap 2: Scraping treści
        st.info("Etap 2/4: Pobieranie treści ze stron przez Scraping API...")
        all_articles_content, successful_sources = [], []
        # Używamy klucza ScrapingBee w wywołaniu funkcji
        progress_bar = st.progress(0)
        for i, result in enumerate(filtered_results):
             url = result.get('link')
             if url: # Upewnij się, że URL istnieje
                 content = scrape_and_clean_content(url, SCRAPINGBEE_API_KEY)
                 if content:
                     all_articles_content.append(content)
                     successful_sources.append({'title': result.get('title', 'Brak tytułu'), 'link': url})
                 progress_bar.progress((i + 1) / len(filtered_results))
        progress_bar.empty() # Ukryj pasek postępu po zakończeniu

        if not all_articles_content:
            st.error("Nie udało się pobrać treści z żadnej ze stron przy użyciu ScrapingBee. Sprawdź klucz API ScrapingBee i limity.")
            st.stop()

        st.success(f"✅ Pomyślnie pobrano treści z {len(all_articles_content)} stron.")


        # Etap 3: Analiza AI
        st.info("Etap 3/4: Generowanie kompleksowego raportu przez AI...")
        aggregated_content = "\n\n---\n\n".join(all_articles_content) # Połącz pobrane treści
        full_report = analyze_content_with_gemini(aggregated_content, keyword)

        if not full_report:
             st.error("Generowanie raportu przez Gemini nie powiodło się.")
             st.stop()


        # Etap 4: Formatowanie wyników
        st.info("Etap 4/4: Formatowanie wyników...")
        report_sections = parse_report(full_report)

        # Upewnij się, że sekcja "Analizowane Źródła" jest poprawnie dodana przez prompt
        # Możemy nadpisać sekcję 7 w słowniku report_sections, aby na pewno wyświetlić pobrane URL-e
        sources_text = "\n".join([f"- [{source['title']}]({source['link']})" for source in successful_sources])
        report_sections["Analizowane Źródła"] = "Poniżej lista adresów URL, których treść została przeanalizowana przez AI:\n" + sources_text


        st.balloons()
        st.success("Audyt SEO gotowy!")

        st.markdown(f"--- \n## Audyt SEO i plan treści dla frazy: '{keyword}'")

        # --- Interfejs z zakładkami ---
        # Nazwy zakładek muszą pasować do kluczy w słowniku report_sections zwróconym przez parse_report
        # i z tytułami sekcji w prompcie do Gemini.
        tab_titles = [
            "Kluczowe Punkty Wspólne",
            "Unikalne i Wyróżniające Się Elementy",
            "Sugerowane Słowa Kluczowe i Semantyka",
            "Proponowana Struktura Artykułu (Szkic)",
            "Sekcja FAQ (Pytania i Odpowiedzi)",
            "Wnioski i Rekomendacje",
            "Analizowane Źródła" # Nowa zakładka dla źródeł
        ]

        # Tworzenie zakładek dynamicznie
        tabs = st.tabs(tab_titles)

        for i, title in enumerate(tab_titles):
            with tabs[i]:
                st.header(title) # Dodaj nagłówek w każdej zakładce dla jasności
                # Użyj get z domyślną wartością na wypadek, gdyby Gemini nie wygenerowało którejś sekcji
                st.markdown(report_sections.get(title, f"Brak danych dla sekcji: '{title}'. Proszę sprawdzić odpowiedź Gemini."))


    # Koniec bloku if st.button("🚀 Wygeneruj..."):
else:
    # Komunikat początkowy przed kliknięciem przycisku
    if keyword:
         st.info(f"Wprowadzono frazę: '{keyword}'. Kliknij przycisk powyżej, aby rozpocząć analizę.")
    # else: komunikat z text_input placeholder wystarczy na początku
