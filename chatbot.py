import pandas as pd
import os
import re
import random
import requests
from dotenv import load_dotenv
import traceback
import time

load_dotenv()

class MovieRecommender:
    def __init__(self, data_dir_path=None):
        print("Initializing recommender (API mode)...")
        self.tmdb_api_key = os.getenv("TMDB_API_KEY")

        if not self.tmdb_api_key:
            print("ERROR: TMDB_API_KEY not found in environment variables!")
            self.api_available = False
            self.genres = {}
            self.languages = {}
            self.image_base_url = "https://image.tmdb.org/t/p/"
            self.image_size = "w185"

            print("API not available. Recommender limited.")
            return
        else:
            self.api_available = True

        self.genres = self._get_tmdb_genres()
        self.languages = self._get_language_codes()
        print(f"Loaded {len(self.genres)} genres and {len(self.languages)} languages from TMDb.")

        self.image_base_url = "https://image.tmdb.org/t/p/"
        self.image_size = "w185"

        self.max_api_pages_to_fetch = 5
        self.delay_between_pages = 0.1


        print("Recommender initialized (API mode).")


    def _get_tmdb_genres(self):
        """Fetches movie genre list from TMDb API."""
        url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={self.tmdb_api_key}&language=en-US"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if 'genres' in data:
                return {genre['name'].lower(): genre['id'] for genre in data['genres']}
            else:
                print("TMDB genre list response format unexpected.")
                return {}
        except requests.exceptions.RequestException as e:
            print(f"Error fetching TMDB genres: {e}")
            return {}


    def _get_language_codes(self):
        """Fetches supported languages list from TMDb API."""
        url = f"https://api.themoviedb.org/3/configuration/languages?api_key={self.tmdb_api_key}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return {lang['english_name'].lower(): lang['iso_639_1'] for lang in data if lang.get('english_name')}
        except requests.exceptions.RequestException as e:
            print(f"Error fetching TMDB languages: {e}")
            return {}


    # Recommend method updated to accept a list of genres
    def recommend(self, genres=None, after=None, before=None, min_runtime=None, max_runtime=None, min_rating=None, language=None, min_votes=None, excluded_genres=None):
        """
        Recommends movies by querying the TMDb API based on criteria,
        fetching multiple pages for a better sample pool.
        Handles multiple genres (AND logic).
        Returns a dictionary with 'recommendations' (list of movie dicts) and 'note' (string).
        """
        if not self.api_available:
             return {
                 "recommendations": [],
                 "note": "Sorry, the movie recommendation system is currently unavailable (API key missing)."
             }

        # --- Build Base API Query Parameters for /discover/movie ---
        params = {
            'api_key': self.tmdb_api_key,
            'language': 'en-US',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 50,
            'include_adult': 'false',
        }

        # Map genres (list) to TMDb API parameters (MODIFIED)
        if genres and isinstance(genres, list) and genres: # Check if it's a non-empty list
             genre_ids = []
             unrecognized_genres = []
             for g in genres:
                  if g and g.lower() in self.genres:
                       genre_ids.append(self.genres[g.lower()])
                  elif g:
                       unrecognized_genres.append(g)

             if genre_ids:
                  # Join genre IDs with a comma for AND logic
                  params['with_genres'] = ','.join(map(str, genre_ids))

             if unrecognized_genres:
                  # If some genres were not recognized, inform the user
                  return {
                      "recommendations": [],
                      "note": f"Sorry, I couldn't recognize all genres ({', '.join(unrecognized_genres)}). Available genres include: {', '.join(self.genres_list[:10])}..."
                  }
             # If genres list was provided but became empty after mapping (e.g., all unrecognized)
             elif not genre_ids and genres:
                  return {
                      "recommendations": [],
                      "note": f"Sorry, I couldn't recognize any of the specified genres ({', '.join(genres)}). Available genres include: {', '.join(self.genres_list[:10])}..."
                  }


        # Keep other filters (after, before, min_rating, language, min_runtime, max_runtime, min_votes, excluded_genres)
        # ... (Add logic for these filters as in the previous version - they remain the same) ...

        if after:
            params['primary_release_date.gte'] = f"{after}-01-01"

        if before:
            params['primary_release_date.lte'] = f"{before}-12-31"

        if min_rating is not None:
             params['vote_average.gte'] = min_rating

        if language and language.lower() in self.languages:
             params['with_original_language'] = self.languages[language.lower()]
        elif language:
             print(f"Warning: Language '{language}' not found in TMDb supported list. Ignoring language filter.")
             pass

        if min_runtime is not None:
             params['with_runtime.gte'] = min_runtime

        if max_runtime is not None:
             params['with_runtime.lte'] = max_runtime

        if min_votes is not None:
             params['vote_count.gte'] = min_votes

        if excluded_genres:
             excluded_genre_ids = [
                 self.genres[g.lower()] for g in excluded_genres
                 if g and g.lower() in self.genres # Check if g is not None/empty and is recognized
             ]
             if excluded_genre_ids:
                  params['without_genres'] = '|'.join(map(str, excluded_genre_ids)) # Using pipe | for OR exclusion
             elif excluded_genres: # If list was provided but all were unrecognized
                  print(f"Warning: None of the requested excluded genres ({', '.join(excluded_genres)}) were recognized.")
                  # Optionally, you could return an error to the user here as well


        # --- Fetch Multiple Pages from API ---
        # ... (This logic remains the same) ...
        api_url = "https://api.themoviedb.org/3/discover/movie"
        all_movies_list = []
        total_pages = 1
        fetched_pages = 0

        print(f"Starting API multi-page fetch for params: {params}")

        while fetched_pages < self.max_api_pages_to_fetch and fetched_pages < total_pages:
            page = fetched_pages + 1
            current_params = params.copy()
            current_params['page'] = page

            try:
                print(f"Fetching page {page}...")
                response = requests.get(api_url, params=current_params)
                response.raise_for_status()
                data = response.json()

                if 'results' in data and data['results']:
                    all_movies_list.extend(data['results'])
                    total_pages = data.get('total_pages', total_pages)
                    fetched_pages += 1
                    print(f"Fetched {len(data['results'])} results from page {page}. Total results so far: {len(all_movies_list)}. Total pages available: {total_pages}.")

                    if fetched_pages < self.max_api_pages_to_fetch and fetched_pages < total_pages:
                         time.sleep(self.delay_between_pages)

                elif 'results' in data and not data['results']:
                     print(f"Page {page} returned no results. Stopping pagination.")
                     break

                else:
                    print(f"Page {page} response format unexpected. Stopping pagination.")
                    break


            except requests.exceptions.RequestException as e:
                print(f"API request failed while fetching page {page}: {e}")
                traceback.print_exc()
                if not all_movies_list:
                     return {
                         "recommendations": [],
                         "note": "Sorry, I'm having trouble fetching movie data from the API right now."
                     }
                else:
                     print("Continuing with partial data due to API error.")
                     break

        print(f"Finished fetching. Total movies collected across {fetched_pages} pages: {len(all_movies_list)}")

        # --- Post-processing and Sampling from the combined list ---
        # ... (This logic remains the same, handling empty results and sampling) ...
        if not all_movies_list:
             return {
                 "recommendations": [],
                 "note": "Sorry, I couldn't find any movies matching all your criteria from the API."
             }

        df_results = pd.DataFrame(all_movies_list)

        if 'id' in df_results.columns:
             df_results = df_results.drop_duplicates(subset=['id'])
             print(f"After removing duplicates: {len(df_results)} unique movies.")

        if df_results.empty:
             return {
                 "recommendations": [],
                 "note": "Sorry, no unique movies found matching your criteria after post-processing API results."
             }

        sample_size = min(5, len(df_results))

        if sample_size > 0:
             sample = df_results.sample(n=sample_size, random_state=random.randint(1, 10000))
        else:
             return {
                  "recommendations": [],
                  "note": "Found matching movies, but couldn't select a sample."
             }


        # --- Prepare Structured Output for Frontend ---
        recommendation_data = []
        for _, row in sample.iterrows():
            genre_names = [
                name.capitalize()
                for name, id in self.genres.items()
                if id in row.get('genre_ids', [])
            ]
            genre_str = ", ".join(genre_names) if genre_names else "Unknown Genre"

            recommendation_data.append({
                "id": row.get('id'),
                "name": row.get('title', 'N/A'),
                "year": row.get('release_date', 'N/A').split('-')[0] if row.get('release_date') else 'N/A',
                "rating": f"{row.get('vote_average'):.1f}" if row.get('vote_average') is not None else 'N/A',
                "genres": genre_str, # This is the combined string for display
                "poster_path": row.get('poster_path'),
                "overview": row.get('overview', 'No overview available.'),
            })

        # Build the note string based on applied filters (MODIFIED for genre list)
        note_parts = []
        if genres and isinstance(genres, list):
             note_parts.append(f"Genres: {', '.join(genres)}") # List all requested genres
        # Keep other notes
        if after: note_parts.append(f"After {after}")
        if before: note_parts.append(f"Before {before}")
        if min_runtime is not None: note_parts.append(f"Min Runtime: {min_runtime} min")
        if max_runtime is not None: note_parts.append(f"Max Runtime: {max_runtime} min")
        if min_rating is not None: note_parts.append(f"Rating >= {min_rating:.1f}")
        if language: note_parts.append(f"Language: {language}")
        if min_votes is not None: note_parts.append(f"Votes >= {min_votes}")
        if excluded_genres: note_parts.append(f"Excluding Genres: {', '.join(excluded_genres)}")


        rating_note = ""
        if note_parts:
             rating_note = " (Filters applied: " + ", ".join(note_parts) + ")"
        elif not recommendation_data:
             rating_note = " (No movies found matching criteria from API)"
        else:
             sample_min_rating = sample['vote_average'].min() if 'vote_average' in sample.columns else None
             if pd.notna(sample_min_rating) and sample_min_rating > 0:
                  rating_note = f" (Showing recommendations rated {sample_min_rating:.1f} or higher from API)"
             else:
                  rating_note = " (Showing matching movies from API)"


        return {
            "recommendations": recommendation_data,
            "note": rating_note
        }


    # Keep property methods
    @property
    def genres_list(self):
        """Returns a sorted list of available genre names."""
        if not self.genres:
            return []
        return sorted([name.capitalize() for name in self.genres.keys()])

    @property
    def languages_list(self):
        """Returns a sorted list of available language names."""
        if not self.languages:
             return []
        return sorted([name.capitalize() for name in self.languages.keys()])