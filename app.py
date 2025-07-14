import os
import random
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# --- Configuration ---
# Remember to set your TMDB API key as an environment variable
# named TMDB_API_KEY.
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
    Fetches a random movie that is available on specified streaming services.
    """
    max_pages_to_try = 5
    for _ in range(max_pages_to_try):
        # Discover popular movies, filtering by genre/keyword if provided
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

            # Check each movie for watch providers
            for movie_data in movies:
                movie_id = movie_data["id"]
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
                
                if available_providers:
                    # Found a movie on one of the target services!
                    return movie_data, available_providers

        except requests.RequestException:
            # If an API call fails, just continue to the next attempt
            continue

    return None, None # Return nothing if no movie was found


@app.route("/")
def index():
    """Renders the main page with genre options."""
    genres = get_genres()
    return render_template("index.html", genres=genres)


@app.route("/select", methods=["POST"])
def select_movie():
    """Handles the user's movie selection and displays a result."""
    movie, providers = None, None
    selection_type = request.form.get("selection_type")
    error = None

    if selection_type == "random":
        movie, providers = get_random_movie()
    elif selection_type == "genre":
        genre_id = request.form.get("genre")
        movie, providers = get_random_movie(genre_id=genre_id)
    elif selection_type == "keyword":
        keyword = request.form.get("keyword")
        if keyword:
            movie, providers = get_random_movie(keyword=keyword)
        else:
            error = "Please enter a keyword."

    if not movie and not error:
        error = "Couldn't find a movie with that criteria. Please try again."

    return render_template(
        "movie.html",
        movie=movie,
        providers=providers,
        poster_base_url=POSTER_BASE_URL,
        logo_base_url=LOGO_BASE_URL,
        error=error,
    )