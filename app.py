from flask import Flask, render_template, request, jsonify
from chatbot import MovieRecommender
import re
import os
import traceback
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DATA_FOLDER = "data"

if not os.path.isdir(DATA_FOLDER):
    print(f"Warning: Data directory '{DATA_FOLDER}' not found. CSV fallback may not work (if implemented).")

recommender = None
try:
    print("Initializing recommender...")
    recommender = MovieRecommender(DATA_FOLDER)
    print("Recommender initialized successfully.")
except Exception as e:
    print(f"ERROR: Failed to initialize MovieRecommender: {e}")
    traceback.print_exc()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/get", methods=["GET"])
def get_bot_response():
    user_msg = request.args.get('msg', '').lower()

    if recommender is None or not recommender.api_available:
        print("Error: Recommender object or API is not available.")
        return jsonify({'response': {"recommendations": [], "note": "Sorry, the movie recommendation system is currently unavailable. Please check API key setup."}})

    # --- Parse all potential filters ---
    # genre = None # No longer a single string
    genres = [] # Changed to a list for multiple genres
    after = None
    before = None
    min_runtime = None
    max_runtime = None
    min_rating = None
    language = None
    min_votes = None
    excluded_genres = []


    # Parse Genres (MODIFIED)
    user_msg_for_genre_parsing = user_msg # Work on a copy
    sorted_genres = sorted(recommender.genres_list, key=len, reverse=True) # Sort by length descending to match longer names first

    for g in sorted_genres:
        # Use regex with word boundaries to find the genre name
        # Check if the genre name exists in the remaining part of the message
        genre_pattern = r'\b' + re.escape(g.lower()) + r'\b'
        if re.search(genre_pattern, user_msg_for_genre_parsing):
            genres.append(g)
            # Replace the found genre name (and potential connecting words)
            # with a placeholder or space to prevent re-matching or interference
            # This is a heuristic and might not be perfect for all sentence structures
            user_msg_for_genre_parsing = re.sub(
                r"(?:\b(?:and|or|,)\s+)?(?:" + genre_pattern + r")",
                " ", # Replace with space
                user_msg_for_genre_parsing
            ).strip()


    # Parse Year Constraints (keep existing logic)
    after_match = re.search(r"\b(after|since|from)\s+(\d{4})\b", user_msg)
    if after_match: after = int(after_match.group(2))

    before_match = re.search(r"\b(before|until|upto)\s+(\d{4})\b", user_msg)
    if before_match: before = int(before_match.group(2))

    # Parse Runtime Constraints (keep existing logic)
    min_runtime_match = re.search(r"\b(at least|min(?:imum)?|over)\s+(\d+)\s*(?:minutes|min|mins)?\b", user_msg)
    if min_runtime_match: min_runtime = int(min_runtime_match.group(2))

    max_runtime_match = re.search(r"\b(?:under|less than|max(?:imum)?|up to)\s+(\d+)\s*(?:minutes|min|mins)?\b", user_msg)
    if max_runtime_match: max_runtime = int(max_runtime_match.group(2))

    # Parse Rating Constraints (keep existing logic)
    rating_match = re.search(r"\b(rated|rating)\s+(above|over|at least|higher than)\s+([0-9.]+)\b", user_msg)
    if rating_match:
        try: min_rating = float(rating_match.group(3))
        except ValueError: pass
    elif min_rating is None and (
        re.search(r'\b(good|great|highly rated|highly-rated|top rated|top-rated|best|awesome|fantastic)\b', user_msg) or
        (genres and len(genres) > 0) # Assume higher rating desired if genres are specified
    ):
         min_rating = 7.0 # Default threshold for "good" or when specific genres are asked for

    # Parse Language (keep existing logic)
    sorted_languages = sorted(recommender.languages_list, key=len, reverse=True)
    for lang_name in sorted_languages:
        if re.search(r'\b(?:in|language)?\s*' + re.escape(lang_name.lower()) + r'\b', user_msg):
            language = lang_name
            break

    # Parse Minimum Vote Count (keep existing logic)
    min_votes_match = re.search(r"\b(?:at least|min(?:imum)?|over)\s+(\d+)\s*votes?\b", user_msg)
    if min_votes_match: min_votes = int(min_votes_match.group(1))

    # Parse Excluded Genres (keep existing logic - uses the original user_msg)
    excluded_match = re.search(r"\b(?:but not|excluding|without)\s+(.+)", user_msg)
    if excluded_match:
        excluded_text = excluded_match.group(1)
        potential_excluded_genres = re.split(r",\s*| and ", excluded_text)

        for excluded_part in potential_excluded_genres:
             excluded_part = excluded_part.strip()
             if not excluded_part: continue

             for g in sorted_genres:
                 if re.search(r'\b' + re.escape(g.lower()) + r'\b', excluded_part):
                     excluded_genres.append(g)
                     # No need to modify excluded_text here, as we only parse this part once


    print(f"Parsed filters: genres={genres}, after={after}, before={before}, min_runtime={min_runtime}, max_runtime={max_runtime}, min_rating={min_rating}, language={language}, min_votes={min_votes}, excluded_genres={excluded_genres}")

    # --- Call the recommender ---
    # Pass the list of genres
    response_data = recommender.recommend(
        genres=genres, # Pass the list
        after=after,
        before=before,
        min_runtime=min_runtime,
        max_runtime=max_runtime,
        min_rating=min_rating,
        language=language,
        min_votes=min_votes,
        excluded_genres=excluded_genres
    )

    return jsonify({'response': response_data})


if __name__ == "__main__":
    app.run(debug=True)