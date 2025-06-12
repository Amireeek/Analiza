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

    # === PONIŻEJ ZMODYFIKOWANY PROMPT OD UŻYTKOWNIKA ===
    # Usunięto sekcje 6 i 7 z listy numerowanej dla Gemini
    prompt = f"""
Jesteś światowej klasy analitykiem SEO i strategiem content marketingu. Twoim zadaniem jest przeanalizowanie dostarczonej treści z czołowych artykułów dla frazy "{keyword_phrase}" i na tej podstawie wygenerowanie kompleksowego raportu w formacie Markdown.

Raport musi być podzielony na DOKŁADNIE następujące sekcje, używając nagłówków `### numer. Nazwa sekcji` i **żadnych innych nagłówków H3 w tytułach sekcji**:

### 1. Kluczowe Punkty Wspólne
(Wypunktuj tematy, podtematy, kluczowe informacje, perspektywy i style narracji, które powtarzają się w większości analizowanych tekstów. Skup się na tym, co jest standardem w TOP 10 i skonstruuj wytyczne dla copywritera)

### 2. Unikalne i Wyróżniające Się Elementy
(Wypunktuj nietypowe, oryginalne, innowacyjne lub szczególnie wartościowe informacje, dane, przykłady, case studies, infografiki (opisz co przedstawiają) lub perspektywy, które pojawiły się tylko w niektórych źródłach i mogą stanowić przewagę konkurencyjną dla nowego artykułu.)

### 3. Sugerowane Słowa Kluczowe i Semantyka
(Na podstawie analizy treści konkurencji, stwórz listę 10-12 najważniejszych słów kluczowych, fraz długoogonowych i pojęć semantycznie powiązanych. Pogrupuj je tematycznie, jeśli to ułatwia zrozumienie. Wskaż intencję wyszukiwania dla frazy głównej.)

### 4. Proponowana Struktura Artykułu (Szkic)
(Zaproponuj idealną, rozbudowaną strukturę nowego artykułu, która uwzględni kluczowe punkty, unikalne elementy i semantykę. Zaproponuj kilka nagłówków do artykułu. Oznasz je jako H2 i H3)

### 5. Sekcja FAQ (Pytania i Odpowiedzi)
(Stwórz listę 4-5 najczęstszych pytań, na które odpowiadają konkurenci, w stylu 'People Also Ask'. Podaj 2-3 zdaniowe bezpośrednie odpowiedzi na te pytania, bazując na analizowanej treści. Odpowiedzi napisz pod pytaniami)


Pamiętaj, aby Twoja odpowiedź była TYLKO treścią raportu w formacie Markdown, bez żadnych dodatkowych wstępów czy podsumowań poza strukturą raportu. Cała odpowiedź musi być w języku polskim.
Treść do analizy:
{all_content}
"""
    # === KONIEC ZMODYFIKOWANEGO PROMPTU ===

    try:
        # Używamy modelu gemini-1.5-flash-latest dla szybkości i kosztów
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)

        # Sprawdzenie, czy odpowiedź zawiera treść
        if hasattr(response, 'text') and response.text:
             return response.text
        else:
             st.warning("⚠️ Gemini zwróciło pustą odpowiedź lub błąd. Spróbuj ponownie lub zmień prompt.")
             # Dodatkowe informacje o błędzie z API Gemini
             if hasattr(response, 'prompt_feedback'):
                 st.write("Feedback z promptu:", response.prompt_feedback)
             if hasattr(response, 'candidates') and response.candidates:
                  if response.candidates[0].finish_reason:
                    st.write("Przyczyna zakończenia generacji przez API:", response.candidates[0].finish_reason)
                  if hasattr(response.candidates[0], 'safety_ratings'):
                     st.write("Oceny bezpieczeństwa:", response.candidates[0].safety_ratings)

             return None


    except Exception as e:
        st.error(f"🛑 Błąd podczas komunikacji z Gemini API: {e}")
        # st.info("Upewnij się, że Twój GEMINI_API_KEY jest poprawny i masz dostęp do modelu 'gemini-1.5-flash-latest'.") # Wskazówka
        return None


# --- Funkcja do parsowania raportu (bez zmian) ---
# Regex nadal działa, bo format nagłówków ### numer. Nazwa sekcji jest zachowany
def parse_report(report_text):
    """Dzieli pełny raport na sekcje do wyświetlenia w zakładkach."""
    if not report_text: return {}
    sections = {}
    # Wyrażenie regularne do znalezienia treści pomiędzy nagłówkami ###
    # Łapie numer, tytuł i treść aż do kolejnego nagłówka ### lub końca tekstu
    # Zmieniono regex, aby był bardziej tolerancyjny na ewentualne pominięcia numeracji,
    # ale wciąż oparty o format ###
    # Nowy regex: `###\s*(?:\d+\.\s*)?(.*?)\n(.*?)(?=\n###\s*|$|\Z)`
    # ###        - szuka dosłownie "###"
    # \s*        - zero lub więcej białych znaków
    # (?:\d+\.\s*)? - opcjonalnie (?:...)? nienumerowana grupa: jedna lub więcej cyfr (\d+) kropka (\.) i białe znaki (\s*)
    # (.*?)      - łapie tytuł sekcji (dowolne znaki, niechciwie) - Grupa 1
    # \n         - znak nowej linii
    # (.*?)      - łapie treść sekcji (dowolne znaki, niechciwie) - Grupa 2
    # (?=\n###\s*|$|\Z) - Pozytywne spojrzenie w przód (lookahead). Szuka, czy dalej jest:
    #   \n###\s* - znak nowej linii, ###, białe znaki (czyli początek kolejnej sekcji)
    #   |        - LUB
    #   $        - koniec linii
    #   |        - LUB
    #   \Z       - koniec stringu (upewnia się, że łapie ostatnią sekcję)
    pattern = r"###\s*(?:\d+\.\s*)?(.*?)\n(.*?)(?=\n###\s*|$|\Z)" # Ulepszony regex

    matches = re.findall(pattern, report_text, re.DOTALL)

    for match in matches:
        # match[0] to tytuł, match[1] to treść
        title = match[0].strip()
        content = match[1].strip()
        if title: # Dodatkowe sprawdzenie, czy tytuł nie jest pusty po strip()
            sections[title] = content # Kluczem słownika jest tytuł sekcji

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
        # Rozszerzona lista domen do banowania
        BANNED_DOMAINS = [
            "youtube.com", "pinterest.", "instagram.com", "facebook.com",
            "olx.pl", "allegro.pl", "twitter.com", "tiktok.com",
            "wikipedia.org", "słownik.pl", "encyklopedia.", "forum.", # Dodano przykładowe filtry ogólne
            ".gov", ".edu" # Często pomijane w analizach komercyjnych
        ]
        # Filtrujemy wyniki, upewniając się, że link istnieje i nie jest None/pusty
        filtered_results = [r for r in top_results if r and r.get('link') and not any(b in r['link'].lower() for b in BANNED_DOMAINS)] # .lower() dla bezpieczeństwa

        if not filtered_results:
            st.error("Po filtracji nie pozostały żadne artykuły do analizy (usunięto strony wideo, social media, sklepy, fora, Wikipedia, itp.).")
            st.stop()

        # Informacja o filtracji
        if len(top_results) > len(filtered_results):
             st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników (wideo/social media/sklepy/fora/Wikipedia/itp.), analizuję {len(filtered_results)} znalezionych artykułów.")

        st.subheader("Analizowane adresy URL (po filtracji):")
        for i, result in enumerate(filtered_results, 1):
             # Dodano zabezpieczenie get() na wypadek braku tytułu, wyświetlamy link jako fallback
            display_title = result.get('title', result.get('link', f"Brak tytułu dla {result.get('link', 'nieznany URL')}"))
            st.write(f"{i}. [{display_title}]({result.get('link', '#')})") # Używamy '#' jako fallback dla linku


        # Etap 2: Scraping treści
        st.info("Etap 2/4: Pobieranie treści ze stron przez Scraping API...")
        all_articles_content, successful_sources = [], []
        # Używamy klucza ScrapingBee w wywołaniu funkcji
        progress_bar = st.progress(0)
        for i, result in enumerate(filtered_results):
             url = result.get('link')
             if url: # Upewnij się, że URL istnieje po filtracji
                 content = scrape_and_clean_content(url, SCRAPINGBEE_API_KEY)
                 if content:
                     all_articles_content.append(content)
                     successful_sources.append({'title': result.get('title', 'Brak tytułu'), 'link': url})
                 progress_bar.progress((i + 1) / len(filtered_results))
        progress_bar.empty() # Ukryj pasek postępu po zakończeniu

        if not all_articles_content:
            st.error("Nie udało się pobrać treści z żadnej ze stron przy użyciu ScrapingBee. Sprawdź klucz API ScrapingBee, limity lub dostępność stron. Czasami problemem są też bardzo rozbudowane strony.")
            st.stop()

        st.success(f"✅ Pomyślnie pobrano treści z {len(all_articles_content)} stron.")


        # Etap 3: Analiza AI
        st.info("Etap 3/4: Generowanie kompleksowego raportu przez AI...")
        aggregated_content = "\n\n---\n\n".join(all_articles_content) # Połącz pobrane treści
        # Przekazujemy zagregowaną treść i frazę kluczową do Gemini
        full_report = analyze_content_with_gemini(aggregated_content, keyword)

        if not full_report:
             st.error("Generowanie raportu przez Gemini nie powiodło się. Sprawdź logi lub spróbuj z inną frazą/kluczami API.")
             st.stop()


        # Etap 4: Formatowanie wyników
        st.info("Etap 4/4: Formatowanie wyników...")
        # Parsowanie odpowiedzi Gemini na sekcje
        report_sections = parse_report(full_report)

        # === RĘCZNE DODANIE SEKcji Z ANALIZOWANYMI ŹRÓDŁAMI ===
        # Zawsze dodajemy tę sekcję do słownika report_sections
        sources_text = "\n".join([f"- [{source['title']}]({source['link']})" for source in successful_sources])
        report_sections["Analizowane Źródła"] = "Poniżej lista adresów URL, których treść została pomyślnie pobrana i przeanalizowana przez AI:\n" + sources_text


        st.balloons()
        st.success("✅ Audyt SEO gotowy!")

        st.markdown(f"--- \n## Audyt SEO i plan treści dla frazy: '{keyword}'")

        # --- Interfejs z zakładkami: DYNAMICZNE TWORZENIE ZAKŁADEK ---
        # Definiujemy preferowaną kolejność wszystkich MOŻLIWYCH zakładek
        preferred_tab_order = [
            "Kluczowe Punkty Wspólne",
            "Unikalne i Wyróżniające Się Elementy",
            "Sugerowane Słowa Kluczowe i Semantyka",
            "Proponowana Struktura Artykułu (Szkic)",
            "Sekcja FAQ (Pytania i Odpowiedzi)",
            "Wnioski i Rekomendacje", # Ta sekcja nie jest generowana przez Gemini w Twoim prompcie, ale może być dodana ręcznie lub usunięta z tej listy.
            "Analizowane Źródła" # Sekcja dodawana ręcznie
        ]

        # Tworzymy listę tytułów zakładek, które faktycznie istnieją w naszym słowniku report_sections,
        # zachowując preferowaną kolejność.
        actual_tab_titles = [
            title for title in preferred_tab_order if title in report_sections
        ]

        # Tworzenie zakładek dynamicznie na podstawie ISTNIEJĄCYCH sekcji
        if actual_tab_titles:
             tabs = st.tabs(actual_tab_titles)

             for i, title in enumerate(actual_tab_titles):
                 with tabs[i]:
                     st.header(title) # Dodaj nagłówek w każdej zakładce dla jasności
                     # Pobierz treść z report_sections (wiemy, że klucz istnieje dzięki filtracji)
                     st.markdown(report_sections[title])
        else:
             st.warning("Brak danych do wyświetlenia w zakładkach. Sprawdź odpowiedź Gemini.")


    # Koniec bloku if st.button("🚀 Wygeneruj..."):
else:
    # Komunikat początkowy przed kliknięciem przycisku
    if keyword:
         st.info(f"Wprowadzono frazę: '{keyword}'. Kliknij przycisk powyżej, aby rozpocząć analizę.")
    # else: komunikat z text_input placeholder wystarczy na początku
