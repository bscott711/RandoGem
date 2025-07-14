import os
import random
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# --- Configuration ---
API_KEY = os.environ.get("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
LOGO_BASE_URL = "https://image.tmdb.org/t/p/w92"

# TMDb Provider IDs for major US services
# Netflix: 8, Disney Plus: 337, Amazon Prime Video: 9, Hulu: 15
TARGET_PROVIDERS = {8, 9, 15, 337}
# --- End Configuration ---


def get_genres():
    """Fetches the list of available movie genres from TMDb."""
    url = f"{BASE_URL}/genre/movie/list?api_key={API_KEY}&language=en-US"
    try:
        response = requests.get(url)
        response.raise_for_status()
        genres_data = response.json()
        return genres_data["genres"]
    except requests.RequestException:
        return None


def get_random_movie(genre_id=None, keyword=None):
    """
    Fetches a random movie, its providers, and its trailer.
    """
    max_pages_to_try = 5
    for _ in range(max_pages_to_try):
        discover_url = f"{BASE_URL}/discover/movie?api_key={API_KEY}"
        discover_url += "&language=en-US&sort_by=popularity.desc"
        discover_url += f"&page={random.randint(1, 100)}"
        discover_url += "&watch_region=US&with_watch_monetization_types=flatrate"

        if genre_id:
            discover_url += f"&with_genres={genre_id}"
        if keyword:
            search_url = (
                f"{BASE_URL}/search/keyword?api_key={API_KEY}&query={keyword}"
            )
            search_response = requests.get(search_url)
            if search_response.status_code == 200:
                results = search_response.json().get("results")
                if results:
                    keyword_id = results[0]["id"]
                    discover_url += f"&with_keywords={keyword_id}"

        try:
            response = requests.get(discover_url)
            response.raise_for_status()
            movies = response.json().get("results", [])

            for movie_data in movies:
                movie_id = movie_data["id"]
                # First, check for valid providers
                providers_url = (
                    f"{BASE_URL}/movie/{movie_id}/watch/providers?api_key={API_KEY}"
                )
                providers_response = requests.get(providers_url)
                if providers_response.status_code != 200:
                    continue
                
                providers_data = providers_response.json().get("results", {})
                us_providers = providers_data.get("US", {}).get("flatrate", [])
                available_providers = [
                    p for p in us_providers if p["provider_id"] in TARGET_PROVIDERS
                ]

                if not available_providers:
                    continue # Skip movie if not on target services

                # --- NEW: Get video data ---
                videos_url = f"{BASE_URL}/movie/{movie_id}/videos?api_key={API_KEY}"
                videos_response = requests.get(videos_url)
                trailer_key = None
                if videos_response.status_code == 200:
                    videos_data = videos_response.json().get("results", [])
                    for video in videos_data:
                        if video["type"] == "Trailer" and video["site"] == "YouTube":
                            trailer_key = video["key"]
                            break # Found the official trailer

                # Return all data for the found movie
                return movie_data, available_providers, trailer_key

        except requests.RequestException:
            continue

    return None, None, None # Return nothing if no movie was found


@app.route("/")
def index():
    """Renders the main page with genre options."""
    genres = get_genres()
    return render_template("index.html", genres=genres)


@app.route("/select", methods=["POST"])
def select_movie():
    """Handles the user's movie selection and displays a result."""
    movie, providers, trailer_key = None, None, None
    selection_type = request.form.get("selection_type")
    error = None

    if selection_type == "random":
        movie, providers, trailer_key = get_random_movie()
    elif selection_type == "genre":
        genre_id = request.form.get("genre")
        movie, providers, trailer_key = get_random_movie(genre_id=genre_id)
    elif selection_type == "keyword":
        keyword = request.form.get("keyword")
        if keyword:
            movie, providers, trailer_key = get_random_movie(keyword=keyword)
        else:
            error = "Please enter a keyword."

    if not movie and not error:
        error = "Couldn't find a movie with that criteria. Please try again."

    return render_template(
        "movie.html",
        movie=movie,
        providers=providers,
        trailer_key=trailer_key,
        poster_base_url=POSTER_BASE_URL,
        logo_base_url=LOGO_BASE_URL,
        error=error,
    )