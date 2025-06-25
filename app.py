# -*- coding: utf-8 -*-

# ==============================================================================
# Krok 0: Instalacja bibliotek
# ==============================================================================
# pip install streamlit requests trafilatura google-generativeai scrapingbee pandas
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
import time
import pandas as pd # Dodano do tworzenia tabel

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
    st.error(f"🛑 Błąd konfiguracji sekretów! Nie znaleziono wymaganego sekretu: {missing_key}.")
    st.stop()
except Exception as e:
    st.error(f"🛑 Wystąpił nieoczekiwany błąd podczas ładowania kluczy: {e}")
    st.stop()

# ==============================================================================
# Krok 4: Funkcje Backendowe
# ==============================================================================

@st.cache_data
def get_serp_data_with_dataforseo(login, password, query, num_results=10, location_code=2616, language_code='pl'):
    # (bez zmian)
    post_data = [{"keyword": query, "location_code": location_code, "language_code": language_code, "depth": num_results}]
    headers = {'Content-Type': 'application/json'}
    endpoint_url = "https://api.dataforseo.com/v3/serp/google/organic/live/regular"
    organic_results_list = []
    try:
        response = requests.post(endpoint_url, auth=(login, password), headers=headers, json=post_data, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data.get("status_code") == 20000 and data.get("tasks") and data["tasks"][0].get("result") and data["tasks"][0]["result"][0].get("items"):
            items = data["tasks"][0]["result"][0]["items"]
            for item in items:
                if item.get("type") == "organic":
                    title, link = item.get("title"), item.get("url")
                    if title and link: organic_results_list.append({'title': title, 'link': link})
        else:
            status_message = data.get("status_message", "Nieznany błąd.")
            tasks_error = ""
            if data.get("tasks") and data["tasks"][0].get("status_message") != "Ok.":
                tasks_error = f" Błąd zadania: {data['tasks'][0]['status_code']} - {data['tasks'][0]['status_message']}"
            st.warning(f"DataForSEO API (SERP) zwróciło nieoczekiwany status lub brak wyników: {status_message}{tasks_error}.")
        return organic_results_list
    except Exception as e:
        st.error(f"🛑 Błąd DataForSEO (SERP): {e}")
        return []

@st.cache_data
def get_keyword_volumes_dataforseo(login, password, keywords_list, location_code=2616, language_code='pl'):
    """Pobiera wolumeny wyszukiwań dla listy słów kluczowych z DataForSEO."""
    if not keywords_list:
        st.write("DEBUG: Lista słów kluczowych do sprawdzenia wolumenu jest pusta.") # Debug
        return {}
    
    # Ograniczenie do unikalnych słów, aby nie dublować zapytań
    unique_keywords = list(set(kw.lower() for kw in keywords_list if kw)) # Upewniamy się, że nie ma pustych stringów

    if not unique_keywords:
        st.write("DEBUG: Lista unikalnych słów kluczowych jest pusta po oczyszczeniu.") # Debug
        return {}

    # DataForSEO pozwala na max 100 słów w jednym zadaniu w tablicy 'keywords'
    # Dzielimy na paczki po 100, jeśli jest więcej
    chunk_size = 100
    keyword_chunks = [unique_keywords[i:i + chunk_size] for i in range(0, len(unique_keywords), chunk_size)]
    
    keyword_volumes = {}
    headers = {'Content-Type': 'application/json'}
    endpoint_url = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
    
    st.write(f"DEBUG: Będę sprawdzać wolumeny dla {len(unique_keywords)} unikalnych słów w {len(keyword_chunks)} paczkach.") # Debug

    for chunk_index, chunk in enumerate(keyword_chunks):
        post_data = [{"keywords": chunk, "location_code": location_code, "language_code": language_code}]
        try:
            st.write(f"DEBUG: Wysyłanie paczki {chunk_index + 1}/{len(keyword_chunks)} o wolumeny: {chunk}") # Debug
            response = requests.post(endpoint_url, auth=(login, password), headers=headers, json=post_data, timeout=60)
            response.raise_for_status()
            data = response.json()
            st.write(f"DEBUG: Odpowiedź JSON (wolumeny, paczka {chunk_index + 1}) od DataForSEO: {data}") # Debug

            if data.get("status_code") == 20000 and data.get("tasks") and data["tasks"][0].get("result"):
                results = data["tasks"][0]["result"]
                for res_item in results:
                    keyword = res_item.get("keyword")
                    search_volume = res_item.get("search_volume")
                    if keyword:
                        keyword_volumes[keyword.lower()] = search_volume if search_volume is not None else "brak danych"
            else:
                status_message = data.get("status_message", "Nieznany błąd.")
                tasks_error = ""
                if data.get("tasks") and data["tasks"][0].get("status_message") != "Ok.":
                    tasks_error = f" Błąd zadania: {data['tasks'][0]['status_code']} - {data['tasks'][0]['status_message']}"
                st.warning(f"DataForSEO API (Search Volume, paczka {chunk_index + 1}) zwróciło nieoczekiwany status: {status_message}{tasks_error}.")
        except Exception as e:
            st.error(f"🛑 Błąd DataForSEO (Search Volume, paczka {chunk_index + 1}): {e}")
            # W przypadku błędu dla paczki, oznaczamy te słowa jako "błąd pobierania"
            for kw_in_chunk in chunk:
                keyword_volumes[kw_in_chunk.lower()] = "błąd pobierania"
        time.sleep(0.3) # Małe opóźnienie między paczkami

    st.write(f"DEBUG: Końcowe wolumeny: {keyword_volumes}") # Debug
    return keyword_volumes


@st.cache_data
def scrape_and_clean_content(url_to_scrape, scrapingbee_api_key):
    # (bez zmian)
    try:
        response = requests.get(
            url='https://app.scrapingbee.com/api/v1/',
            params={'api_key': scrapingbee_api_key, 'url': url_to_scrape, 'premium_proxy': 'true', 'block_resources': 'false'},
            timeout=90
        )
        response.raise_for_status(); extracted_text = extract(response.text, include_comments=False, include_tables=False, include_images=False)
        if not extracted_text: return None
        cleaned_text = re.sub(r'\s+', ' ', extracted_text).strip()
        return cleaned_text if len(cleaned_text) > 100 else None
    except: return None

def generate_gemini_response(section_prompt, section_name):
    # (bez zmian)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        generation_config = genai.types.GenerationConfig(max_output_tokens=8192)
        response = model.generate_content(section_prompt, generation_config=generation_config)
        if hasattr(response, 'text') and response.text: return response.text.strip()
        else:
            st.warning(f"⚠️ Gemini pusty wynik dla: {section_name}. Feedback: {getattr(response, 'prompt_feedback', 'N/A')}, Zakończenie: {getattr(response.candidates[0] if response.candidates else None, 'finish_reason', 'N/A')}")
            return f"### {section_name}\nBrak danych od AI."
    except Exception as e:
        st.error(f"🛑 Błąd Gemini dla {section_name}: {e}")
        return f"### {section_name}\nBłąd generowania."

def generate_kluczowe_punkty(all_content, keyword_phrase):
    # (bez zmian)
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}". Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 1. Kluczowe Punkty Wspólne". Wypunktuj tematy, podtematy, kluczowe informacje, perspektywy i style narracji, które powtarzają się w większości analizowanych tekstów. Skup się na tym, co jest standardem i skonstruuj wytyczne dla copywritera. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 1. Kluczowe Punkty Wspólne`. Treść do analizy:\n{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}"""
    return generate_gemini_response(prompt, "1. Kluczowe Punkty Wspólne")

def generate_unikalne_elementy(all_content, keyword_phrase):
    # (bez zmian)
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}". Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 2. Unikalne i Wyróżniające Się Elementy". Wypunktuj nietypowe, oryginalne, innowacyjne lub szczególnie wartościowe informacje, dane, przykłady, case studies, infografiki (opisz co przedstawiają) lub perspektywy, które pojawiły się tylko w niektórych źródłach z TOP10 i mogą stanowić przewagę konkurencyjną dla nowego artykułu. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 2. Unikalne i Wyróżniające Się Elementy`. Treść do analizy:\n{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}"""
    return generate_gemini_response(prompt, "2. Unikalne i Wyróżniające Się Elementy")

def generate_słowa_kluczowe_initial_for_table(all_content, keyword_phrase):
    """Generuje WSTĘPNĄ listę słów kluczowych przez Gemini, z myślą o tabeli."""
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}".
Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 3. Sugerowane Słowa Kluczowe i Semantyka".
Na podstawie analizy treści konkurencji z TOP10, stwórz listę 10-15 najważniejszych słów kluczowych i fraz długoogonowych. Możesz je pogrupować tematycznie, używając nagłówków H4 (#### Nazwa Grupy) jeśli to konieczne.
Każde słowo kluczowe lub fraza powinno być w osobnej linii, poprzedzone myślnikiem (np. `- Moje słowo kluczowe`).
Nie dodawaj żadnych dodatkowych opisów ani intencji wyszukiwania bezpośrednio przy słowach kluczowych na liście. Zachowaj czystą listę fraz.
Wskaż ogólną intencję wyszukiwania dla frazy głównej "{keyword_phrase}" w jednym zdaniu na końcu sekcji, po liście słów.
Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 3. Sugerowane Słowa Kluczowe i Semantyka`.

Treść do analizy:
{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}
"""
    return generate_gemini_response(prompt, "3. Sugerowane Słowa Kluczowe i Semantyka (Wstępne)")

def generate_struktura_artykulu(all_content, keyword_phrase):
    # (bez zmian)
    prompt = f"""Jako ekspert SEO specjalizujący się w tworzeniu BARDZO SZCZEGÓŁOWYCH i WYCZERPUJĄCYCH konspektów artykułów, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}". Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 4. Proponowana Struktura Artykułu (Szkic)". Zaproponuj niezwykle rozbudowaną i dogłębną strukturę nowego artykułu w formacie Markdown. Struktura MUSI zawierać: 1. Co najmniej 2-3 propozycje chwytliwych tytułów dla całego artykułu, odpowiednich dla frazy "{keyword_phrase}". 2. Następnie, struktura MUSI być podzielona na **DOKŁADNIE 5 do 6 (pięć do sześciu) GŁÓWNYCH SEKCJI (każda jako nagłówek H2)**. 3. Dla **KAŻDEJ z tych głównych sekcji H2, MUSISZ zaproponować **DOKŁADNIE 3 do 4 (trzy do czterech) bardziej szczegółowych podpunktów (każdy jako nagłówek H3)**. Nagłówki H2 i H3 powinny być angażujące, precyzyjnie opisywać zawartość danego fragmentu i naturalnie zawierać słowa kluczowe, jeśli to możliwe. Dbaj o logiczny przepływ i kompleksowe pokrycie tematu, czerpiąc inspirację z analizy TOP10. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 4. Proponowana Struktura Artykułu (Szkic)`. Treść do analizy:\n{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}"""
    return generate_gemini_response(prompt, "4. Proponowana Struktura Artykułu (Szkic)")

def generate_faq(all_content, keyword_phrase):
    # (bez zmian)
    prompt = f"""Jako analityk SEO, przeanalizuj poniższą treść z artykułów TOP10 dla frazy "{keyword_phrase}". Twoim zadaniem jest TYLKO wygenerowanie sekcji "### 5. Sekcja FAQ (Pytania i Odpowiedzi)". Stwórz listę 4-5 najczęstszych pytań, na które odpowiadają konkurenci z TOP10, w stylu 'People Also Ask'. **Dla każdego pytania, podaj 2-3 zdaniową bezpośrednią odpowiedź, pisząc ją BEZPOŚREDNIO POD DANYM PYTANIEM, w nowej linii.** Użyj formatowania Markdown: pytanie jako zwykły tekst lub pogrubiony, a odpowiedź pod nim. Odpowiedź musi być TYLKO treścią tej sekcji, zaczynając od nagłówka `### 5. Sekcja FAQ (Pytania i Odpowiedzi)`. Treść do analizy:\n{all_content if all_content else "Brak treści z artykułów TOP10 do analizy."}"""
    return generate_gemini_response(prompt, "5. Sekcja FAQ (Pytania i Odpowiedzi)")

def parse_report(report_text):
    # (bez zmian)
    if not report_text: return {}
    sections = {}
    pattern = r"###\s*(?:\d+\.\s*)?(.*?)\n(.*?)(?=\n###\s*\d+\.|$|\Z)"
    matches = re.findall(pattern, report_text, re.DOTALL)
    for match in matches:
        title, content = match[0].strip(), match[1].strip()
        if title and content: sections[title] = content
    return sections

# ==============================================================================
# Krok 5: Interfejs Użytkownika i główna logika
# ==============================================================================
keyword = st.text_input("Wprowadź frazę kluczową, którą chcesz przeanalizować:", placeholder="np. jak dbać o buty skórzane")

if st.button("🚀 Wygeneruj Kompleksowy Audyt SEO"):
    if not keyword: st.warning("Proszę wpisać frazę kluczową."); st.stop()
    if not all(k in st.secrets for k in ["SCRAPINGBEE_API_KEY", "GEMINI_API_KEY", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"]):
        st.error("Błąd: Nie wszystkie wymagane klucze API są skonfigurowane."); st.stop()

    with st.spinner("Przeprowadzam pełny audyt..."):
        st.info("Etap 1/4: Pobieranie wyników z Google (DataForSEO)...")
        top_results = get_serp_data_with_dataforseo(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD, keyword)
        if not top_results: st.error(f"Nie udało się pobrać wyników organicznych dla '{keyword}'."); st.stop()

        BANNED_DOMAINS = ["youtube.com", "pinterest.", "instagram.com", "facebook.com", "olx.pl", "allegro.pl", "twitter.com", "tiktok.com", "wikipedia.org", "słownik.pl", "encyklopedia.", "forum.", ".gov", ".edu", "otodom.pl", "gratka.pl", "domiporta.pl"]
        filtered_results = [r for r in top_results if r and r.get('link') and not any(b in r['link'].lower() for b in BANNED_DOMAINS)]
        if not filtered_results: st.error("Po filtracji brak artykułów do analizy."); st.stop()
        if len(top_results) > len(filtered_results): st.info(f"Pominięto {len(top_results) - len(filtered_results)} wyników, analizuję {len(filtered_results)}.")
        st.subheader("Analizowane adresy URL (po filtracji):")
        for i, r in enumerate(filtered_results, 1): st.write(f"{i}. [{r.get('title', r.get('link'))}]({r.get('link', '#')})")

        all_articles_content_str = ""
        if filtered_results:
            st.info("Etap 2/4: Pobieranie treści ze stron (ScrapingBee)...")
            all_articles_content_list, progress_bar = [], st.progress(0)
            for i, res in enumerate(filtered_results):
                if url := res.get('link'):
                    if content := scrape_and_clean_content(url, SCRAPINGBEE_API_KEY): all_articles_content_list.append(content)
                progress_bar.progress((i + 1) / len(filtered_results))
            progress_bar.empty()
            if not all_articles_content_list: st.warning("Nie udało się pobrać treści z żadnej strony.")
            else: st.success(f"✅ Pobr. treści z {len(all_articles_content_list)} stron."); all_articles_content_str = "\n\n---\n\n".join(all_articles_content_list)
        
        if not all_articles_content_str and not filtered_results: st.error("Brak treści do analizy."); st.stop()

        st.info("Etap 3/4: Generowanie raportu przez AI (Gemini)...")
        report_parts, report_progress = [], st.progress(0)
        
        sections_definitions_no_kw = [
            ("1. Kluczowe Punkty Wspólne", lambda: generate_kluczowe_punkty(all_articles_content_str, keyword)),
            ("2. Unikalne i Wyróżniające Się Elementy", lambda: generate_unikalne_elementy(all_articles_content_str, keyword)),
            ("4. Proponowana Struktura Artykułu (Szkic)", lambda: generate_struktura_artykulu(all_articles_content_str, keyword)),
            ("5. Sekcja FAQ (Pytania i Odpowiedzi)", lambda: generate_faq(all_articles_content_str, keyword))
        ]
        total_steps_for_progress = len(sections_definitions_no_kw) + 2 # +2 dla dwóch kroków generowania sekcji 3

        current_step = 0
        for title, func in sections_definitions_no_kw:
            if title == "4. Proponowana Struktura Artykułu (Szkic)": # Wstawienie sekcji 3 przed sekcją 4
                current_step += 1
                st.write("Generowanie: 3. Sugerowane Słowa Kluczowe i Semantyka (krok 1/2 - sugestie AI)...")
                gemini_keywords_text = generate_słowa_kluczowe_initial_for_table(all_articles_content_str, keyword)
                report_progress.progress(current_step / total_steps_for_progress)
                time.sleep(0.1) # Krótkie opóźnienie

                extracted_keywords_list, table_data, other_text_lines = [], [], []
                if gemini_keywords_text and "Brak danych" not in gemini_keywords_text and "Błąd generowania" not in gemini_keywords_text:
                    st.write(f"DEBUG: Gemini (słowa kluczowe initial):\n{gemini_keywords_text}") # Debug
                    kw_pattern = re.compile(r"^\s*[-*]\s+(.+)$") # Prostszy regex, tylko dla myślników/gwiazdek
                    temp_group_name = ""
                    for line in gemini_keywords_text.split('\n'):
                        if line.startswith("### 3."): continue # Pomiń główny nagłówek sekcji
                        if line.startswith("#### "): temp_group_name = line.replace("#### ","").strip(); continue # Złap nazwę grupy

                        match = kw_pattern.match(line)
                        if match:
                            kw = match.group(1).strip()
                            if kw: extracted_keywords_list.append(kw); table_data.append({"Grupa": temp_group_name, "Słowo kluczowe": kw, "Szac. wyszukań/mc": "pobieranie..."})
                        elif not match and line.strip(): other_text_lines.append(line.strip()) # Zbieramy pozostały tekst, np. intencję

                final_section_3_content = "### 3. Sugerowane Słowa Kluczowe i Semantyka\n"
                if extracted_keywords_list:
                    current_step += 1
                    st.write(f"Generowanie: 3. Sugerowane Słowa Kluczowe i Semantyka (krok 2/2 - wolumeny dla {len(extracted_keywords_list)} fraz)...")
                    keyword_volumes_map = get_keyword_volumes_dataforseo(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD, extracted_keywords_list)
                    report_progress.progress(current_step / total_steps_for_progress)
                    
                    for row in table_data: # Aktualizujemy wolumeny w przygotowanych danych tabeli
                        row["Szac. wyszukań/mc"] = keyword_volumes_map.get(row["Słowo kluczowe"].lower(), "brak danych")
                    
                    df = pd.DataFrame(table_data)
                    # Konwertujemy DataFrame do Markdown tabeli, ale bez indeksu i z ładniejszymi nagłówkami
                    final_section_3_content += df.to_markdown(index=False) + "\n\n"
                elif table_data: # Jeśli były jakieś słowa, ale nie udało się pobrać wolumenów
                    df = pd.DataFrame(table_data) # Wyświetl tabelę z "pobieranie..."
                    final_section_3_content += df.to_markdown(index=False) + "\n\n"
                else: final_section_3_content += "Nie udało się wygenerować lub wyekstrahować słów kluczowych.\n\n"
                
                if other_text_lines: final_section_3_content += "\n".join(other_text_lines) # Dodajemy pozostały tekst (np. intencję)
                report_parts.append(final_section_3_content)
            
            current_step += 1
            st.write(f"Generowanie: {title}...")
            report_parts.append(func())
            report_progress.progress(current_step / total_steps_for_progress)
            time.sleep(0.1)
        
        full_report = "\n\n".join(report_parts)
        report_progress.empty()
        if not full_report or all("Brak danych" in p or "Błąd generowania" in p for p in report_parts):
             st.error("Generowanie raportu nie powiodło się."); st.stop()

        st.info("Etap 4/4: Formatowanie wyników...")
        report_sections = parse_report(full_report)
        
        st.balloons(); st.success("✅ Audyt SEO gotowy!")
        st.markdown(f"--- \n## Audyt SEO i plan treści dla frazy: '{keyword}'")

        preferred_tab_order = ["Kluczowe Punkty Wspólne", "Unikalne i Wyróżniające Się Elementy", "Sugerowane Słowa Kluczowe i Semantyka", "Proponowana Struktura Artykułu (Szkic)", "Sekcja FAQ (Pytania i Odpowiedzi)"]
        actual_tab_titles = [t for t in preferred_tab_order if t in report_sections and report_sections[t].strip()]
        if actual_tab_titles:
            tabs = st.tabs(actual_tab_titles)
            for i, tab_title in enumerate(actual_tab_titles):
                with tabs[i]: st.header(tab_title); st.markdown(report_sections[tab_title])
        else: st.warning("Brak danych do wyświetlenia w zakładkach.")
else:
    if keyword: st.info(f"Wprowadzono frazę: '{keyword}'. Kliknij przycisk powyżej, aby rozpocząć analizę.")
