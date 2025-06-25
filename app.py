
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
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SEARCH_API_KEY = st.secrets["SEARCH_API_KEY"]
    SEARCH_ENGINE_ID = st.secrets["SEARCH_ENGINE_ID"]
    SCRAPINGBEE_API_KEY = st.secrets["SCRAPINGBEE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError as e:
    st.error(f"🛑 Błąd konfiguracji sekretów! Nie znaleziono wymaganego sekretu: {e}. Upewnij się, że skonfigurowałeś WSZYSTKIE 4 sekrety (GEMINI_API_KEY, SEARCH_API_KEY, SEARCH_ENGINE_ID, SCRAPINGBEE_API_KEY) w ustawieniach Streamlit.")
    st.stop()
except Exception as e:
    st.error(f"🛑 Wystąpił nieoczekiwany błąd podczas ładowania kluczy: {e}")
    st.stop()


# ==============================================================================
# Krok 4: Funkcje Backendowe
# ==============================================================================

@st.cache_data
def get_top_10_results(api_key, cse_id, query):
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
    except requests.exceptions.RequestException as e:
        st.warning(f"⚠️ Nie udało się pobrać treści z {url_to_scrape} (ScrapingBee): {e}")
        return None
    except Exception as e:
        st.warning(f"⚠️ Wystąpił nieoczekiwany błąd podczas przetwarzania treści z {url_to_scrape}: {e}")
        return None


@st.cache_data(show_spinner="AI analizuje treść...")
def analyze_content_with_gemini(all_content, keyword_phrase):
    """Analizuje zagregowaną treść i generuje raport z Gemini."""
    if not all_content:
        return "Brak treści do analizy przez AI."

    # <<< ZMIANA: JESZCZE BARDZIEJ PRECYZYJNY PROMPT >>>
    prompt = f"""
Jesteś światowej klasy analitykiem SEO i strategiem content marketingu. Twoim zadaniem jest przeanalizowanie dostarczonej treści z czołowych artykułów dla frazy "{keyword_phrase}" i na tej podstawie wygenerowanie kompleksowego raportu w formacie Markdown.

Twoja odpowiedź MUSI być podzielona na DOKŁADNIE 5 sekcji, używając nagłówków w formacie `### [Numer]. [Nazwa Sekcji]`. Nie używaj żadnych innych nagłówków H3 w tytułach sekcji raportu.

### 1. Kluczowe Punkty Wspólne
Wypunktuj tematy, podtematy i kluczowe informacje, które powtarzają się w większości analizowanych tekstów. Skup się na tym, co jest absolutnym standardem w TOP 10 i musi znaleźć się w nowym artykule.

### 2. Unikalne i Wyróżniające Się Elementy
Wypunktuj nietypowe, oryginalne, innowacyjne lub szczególnie wartościowe informacje (dane, przykłady, case studies, perspektywy), które pojawiły się tylko w niektórych źródłach. To są elementy, które mogą dać przewagę konkurencyjną.

### 3. Sugerowane Słowa Kluczowe i Semantyka
Stwórz listę 10-15 najważniejszych słów kluczowych, fraz długoogonowych i pojęć semantycznie powiązanych. Pogrupuj je tematycznie. Określ intencję wyszukiwania dla frazy głównej (np. informacyjna, komercyjna, transakcyjna).

### 4. Proponowana Struktura Artykułu (Szkic)
To jest najważniejsza sekcja. Stwórz ROZBUDOWANY i KOMPLETNY plan artykułu w formacie Markdown. Twoja odpowiedź dla tej sekcji MUSI zawierać:
1.  Jeden chwytliwy tytuł (jako nagłówek H1, np. `# Tytuł Artykułu`).
2.  Krótki, angażujący wstęp (2-3 zdania).
3.  Listę co najmniej 4-5 głównych sekcji artykułu (jako nagłówki H2, np. `## Nagłówek Sekcji Głównej`).
4.  Dla każdej sekcji H2, zaproponuj 2-4 podpunkty lub tematy do omówienia (jako nagłówki H3, np. `### Podpunkt w Sekcji`).
Struktura musi być logiczna i wyczerpująca.

### 5. Sekcja FAQ (Pytania i Odpowiedzi)
Stwórz listę 4-5 najczęstszych pytań w stylu 'People Also Ask'. Pod każdym pytaniem podaj zwięzłą, 2-3 zdaniową odpowiedź opartą na przeanalizowanej treści.

Pamiętaj, aby Twoja odpowiedź była TYLKO treścią raportu w formacie Markdown, bez żadnych dodatkowych wstępów czy podsumowań poza wymaganą strukturą. Cała odpowiedź musi być w języku polskim.
Treść do analizy:
{all_content}
"""
    # === KONIEC ZMODYFIKOWANEGO PROMPTU ===

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        if hasattr(response, 'text') and response.text:
             return response.text
        else:
             st.warning("⚠️ Gemini zwróciło pustą odpowiedź lub błąd. Szczegóły poniżej.")
             if hasattr(response, 'prompt_feedback'):
                 st.write("Feedback z promptu:", response.prompt_feedback)
             if hasattr(response, 'candidates') and response.candidates and response.candidates[0].finish_reason:
                 st.write("Przyczyna zakończenia generacji przez API:", response.candidates[0].finish_reason)
             return None
    except Exception as e:
        st.error(f"🛑 Błąd podczas komunikacji z Gemini API: {e}")
        return None


# <<< ZMIANA KRYTYCZNA: POPRAWIONY PARSER >>>
def parse_report(report_text):
    """Dzieli pełny raport na sekcje, aby uniknąć kolizji z nagłówkami H3 w szkicu."""
    if not report_text: return {}
    sections = {}
    # Wyrażenie regularne szuka teraz nagłówka sekcji, który MUSI zaczynać się od ###, spacji, cyfry i kropki.
    # Dzięki temu ignoruje nagłówki H3 (`### Tekst`) wewnątrz szkicu artykułu.
    pattern = r"###\s*(\d+\.\s*.*?)\n(.*?)(?=\n###\s*\d+\.|$)"

    matches = re.findall(pattern, report_text, re.DOTALL | re.MULTILINE)

    for match in matches:
        # Tytuł teraz zawiera numer, np. "1. Kluczowe Punkty Wspólne"
        title = match[0].strip()
        content = match[1].strip()
        if title:
            # Usuwamy numerację z klucza słownika dla spójności z listą preferred_tab_order
            clean_title = re.sub(r"^\d+\.\s*", "", title)
            sections[clean_title] = content

    # Jeśli parser nic nie znalazł (bo np. AI nie użyło numeracji), spróbuj starej metody jako fallback
    if not sections:
        pattern_fallback = r"###\s*(.*?)\n(.*?)(?=\n###\s*|$)"
        matches_fallback = re.findall(pattern_fallback, report_text, re.DOTALL | re.MULTILINE)
        for match in matches_fallback:
            title = match[0].strip()
            content = match[1].strip()
            if title and not title.startswith('#'): # Dodatkowe zabezpieczenie
                sections[title] = content

    return sections


# ==============================================================================
# Krok 5: Interfejs Użytkownika Streamlit i główna logika
# ==============================================================================

keyword = st.text_input("Wprowadź frazę kluczową, którą chcesz przeanalizować:", placeholder="np. jak dbać o buty skórzane")

if st.button("🚀 Wygeneruj Kompleksowy Audyt SEO"):
    if not keyword:
        st.warning("Proszę wpisać frazę kluczową.")
        st.stop()

    if not all(k in st.secrets for k in ["GEMINI_API_KEY", "SEARCH_API_KEY", "SEARCH_ENGINE_ID", "SCRAPINGBEE_API_KEY"]):
         st.error("Błąd: Nie wszystkie klucze API są skonfigurowane w Streamlit Secrets.")
         st.stop()

    with st.spinner("Przeprowadzam pełny audyt... To może potrwać kilka minut."):
        st.info("Etap 1/4: Pobieranie i filtrowanie wyników z Google...")
        top_results = get_top_10_results(SEARCH_API_KEY, SEARCH_ENGINE_ID, keyword)
        if not top_results:
            st.error(f"Nie znaleziono żadnych wyników TOP 10 dla frazy: '{keyword}'.")
            st.stop()

        BANNED_DOMAINS = ["youtube.com", "pinterest.", "instagram.com", "facebook.com", "olx.pl", "allegro.pl", "twitter.com", "tiktok.com", "wikipedia.org", ".gov", ".edu"]
        filtered_results = [r for r in top_results if r and r.get('link') and not any(b in r['link'].lower() for b in BANNED_DOMAINS)]

        if not filtered_results:
            st.error("Po filtracji nie pozostały żadne artykuły do analizy.")
            st.stop()

        st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników, analizuję {len(filtered_results)} znalezionych artykułów.")
        with st.expander("Zobacz analizowane adresy URL"):
            for i, result in enumerate(filtered_results, 1):
                display_title = result.get('title', result.get('link', 'Brak tytułu'))
                st.write(f"{i}. [{display_title}]({result.get('link', '#')})")

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

        average_word_count = sum(len(text.split()) for text in all_articles_content) // len(all_articles_content) if all_articles_content else 0

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

        if average_word_count > 0:
            st.metric(label="Średnia długość analizowanych artykułów", value=f"~ {average_word_count} słów")
            st.markdown("---")

        preferred_tab_order = ["Kluczowe Punkty Wspólne", "Unikalne i Wyróżniające Się Elementy", "Sugerowane Słowa Kluczowe i Semantyka", "Proponowana Struktura Artykułu (Szkic)", "Sekcja FAQ (Pytania i Odpowiedzi)", "Analizowane Źródła"]
        
        # <<< ZMIANA: Lepsze dopasowanie nazw zakładek do tego, co zwraca parser >>>
        # Sprawdzamy, czy klucze ze słownika `report_sections` pasują do `preferred_tab_order`
        actual_tab_titles = [title for title in preferred_tab_order if title in report_sections and report_sections[title].strip()]
        
        # Jeśli parser zwrócił klucze z numeracją (np. "1. Kluczowe..."), a w preferred_tab_order mamy bez, to by nie zadziałało.
        # Dlatego parser teraz usuwa numerację z klucza.

        if actual_tab_titles:
             tabs = st.tabs(actual_tab_titles)
             for i, tab in enumerate(tabs):
                 with tab:
                     current_title = actual_tab_titles[i]
                     st.header(current_title)
                     st.markdown(report_sections[current_title], unsafe_allow_html=True) # Dodano unsafe_allow_html dla pewności
        elif report_sections:
             st.warning("Nie udało się dopasować sekcji raportu do zakładek. Wyświetlam cały raport poniżej.")
             st.markdown(full_report)
        else:
             st.warning("Brak danych do wyświetlenia. Odpowiedź z AI mogła być pusta lub w nieprawidłowym formacie.")


else:
    if keyword:
         st.info(f"Wprowadzono frazę: '{keyword}'. Kliknij przycisk powyżej, aby rozpocząć analizę.")

Krok 2: Jak wymusić odświeżenie analizy

Teraz, gdy kod jest poprawiony, musisz upewnić się, że Streamlit nie użyje starego wyniku. Masz dwie opcje:

Opcja A (Najprostsza): Użyj innej frazy kluczowej.
Wpisz w pole do analizy frazę, której jeszcze nie używałeś, np. "najlepszy ekspres do kawy" zamiast "jak dbać o buty". Ponieważ argumenty funkcji analyze_content_with_gemini będą inne (keyword_phrase się zmieni), Streamlit będzie musiał wykonać ją od nowa.

Opcja B (Uniwersalna): Wyczyść pamięć podręczną (cache).

Uruchom aplikację.

W prawym górnym rogu okna aplikacji kliknij na ikonę "hamburgera" (trzy poziome kreski).

Wybierz z menu opcję "Clear cache".

Po wyczyszczeniu cache'u uruchom analizę dla dowolnej frazy (nawet tej samej co wcześniej). Aplikacja będzie zmuszona wykonać wszystkie obliczenia od nowa, używając już poprawionego kodu.

Po wykonaniu tych dwóch kroków (aktualizacja kodu i odświeżenie cache/zmiana frazy), powinieneś otrzymać znacznie bardziej rozbudowaną i zgodną z oczekiwaniami strukturę artykułu.
