from urllib.parse import urlencode as encode_query_params # Dodaj ten import na górze pliku, jeśli go nie ma

@st.cache_data # Cache'owanie wyników wyszukiwania
def get_top_10_google_results_with_scrapingbee(api_key_sb, query, num_results=10, country_code='pl', language_code='pl'):
    """Pobiera wyniki wyszukiwania Google używając API ScrapingBee poprzez scrapowanie URL-a Google SERP."""

    sanitized_query = query.strip()
    if sanitized_query.endswith('?'):
        sanitized_query = sanitized_query[:-1].strip()

    # 1. Skonstruuj URL wyszukiwania Google
    google_search_params = {
        'q': sanitized_query,
        'hl': language_code,      # Język interfejsu Google
        'gl': country_code,       # Geolokalizacja dla wyników Google
        'num': str(num_results)   # Liczba wyników
    }
    google_search_url = f"https://www.google.com/search?{encode_query_params(google_search_params)}"
    st.write(f"Skonstruowany URL Google Search: {google_search_url}") # Debug

    # 2. Parametry dla ScrapingBee
    params_sb = {
        'api_key': api_key_sb,
        'url': google_search_url,      # Przekazujemy pełny URL Google SERP
        'custom_google': 'true',       # Informujemy ScrapingBee, że to domena Google
        'premium_proxy': 'true',       # Zalecane dla Google
        'country_code': country_code,  # Lokalizacja proxy ScrapingBee (powinna pasować do 'gl' w URL Google)
        # 'render_js': 'false'        # Zazwyczaj niepotrzebne dla SERP, może zmniejszyć koszt. Można odkomentować.
        # 'language' dla ScrapingBee może ustawiać nagłówki Accept-Language przez proxy, co też może być pomocne
        # 'language': language_code, # Można rozważyć pozostawienie lub usunięcie, skoro hl jest w URL Google
    }
    
    # Parametr 'nb_results' był dla trybu 'search', teraz liczbę wyników kontroluje 'num' w URL-u Google.
    # Usuwamy 'search' i 'nb_results' z params_sb, bo teraz używamy 'url'.
    # Parametr 'language' dla ScrapingBee może być przydatny do ustawienia nagłówków przez proxy.
    # Warto by było sprawdzić, czy 'language' w ScrapingBee params i 'hl' w Google URL nie kolidują lub czy jedno nie jest ważniejsze.
    # Na razie zostawię 'language' zakomentowane w params_sb, bo 'hl' w URL Google jest bardziej bezpośrednie.


    endpoint_url = 'https://app.scrapingbee.com/api/v1/'

    try:
        st.write(f"Wysyłanie zapytania do ScrapingBee z parametrami: {params_sb}") # Debug
        response = requests.get(endpoint_url, params=params_sb, timeout=90) # Zwiększony timeout
        response.raise_for_status()
        data = response.json()
        st.write(f"Odpowiedź JSON od ScrapingBee: {data}") # Debug

        # Struktura odpowiedzi ScrapingBee przy scrapowaniu Google SERP może być inna
        # niż przy ich dedykowanym parametrze 'search' (jeśli taki tryb istnieje i działał inaczej).
        # Trzeba będzie sprawdzić, czy 'organic_results' nadal jest poprawnym kluczem.
        if 'organic_results' in data and data['organic_results']:
            results = []
            for item in data['organic_results']:
                title = item.get('title')
                link = item.get('link')
                if title and link:
                    results.append({'title': title, 'link': link})
                else:
                    st.warning(f"Pominięto wynik z ScrapingBee z powodu braku tytułu lub linku: {item}")
            return results
        elif 'error' in data: # Sprawdź, czy ScrapingBee nie zwróciło własnego błędu w JSON
             st.warning(f"ScrapingBee zwróciło błąd w odpowiedzi JSON: {data.get('error_message', data['error'])}")
             return []
        else: # Jeśli nie ma 'organic_results' ani 'error', wyświetl ostrzeżenie.
            st.warning(f"ScrapingBee nie zwróciło 'organic_results' dla zapytania (URL: {google_search_url}). Sprawdź odpowiedź JSON powyżej.")
            return []

    except requests.exceptions.Timeout:
        st.error(f"🛑 Przekroczono czas oczekiwania na odpowiedź od ScrapingBee dla URL: '{google_search_url}'")
        return None
    except requests.exceptions.RequestException as e:
        safe_params_for_log = params_sb.copy()
        safe_params_for_log['api_key'] = "REDACTED_API_KEY"
        # URL jest już w params_sb, więc nie trzeba go dodatkowo kodować do logów
        st.error(f"🛑 Błąd podczas komunikacji z API ScrapingBee: {e}. Parametry wysłane (z zredagowanym kluczem): {safe_params_for_log}")
        return None
    except Exception as e:
        st.error(f"🛑 Nieoczekiwany błąd podczas przetwarzania odpowiedzi z ScrapingBee (np. błąd JSON): {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            st.text_area("Surowa odpowiedź (debug):", response.text, height=150)
        return None
