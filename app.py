import os
import random
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# --- Configuration ---
API_KEY = os.environ.get("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
LOGO_BASE_URL = "https://image.tmdb.org/t/p/w92"
PROFILE_BASE_URL = "https://image.tmdb.org/t/p/w185"

# TMDb Provider IDs for major US services
TARGET_PROVIDERS = {8, 9, 15, 337}  # Netflix, Prime, Hulu, Disney+
# --- End Configuration ---


def get_genres():
    """Fetches the list of available movie genres from TMDb."""
    url = f"{BASE_URL}/genre/movie/list?api_key={API_KEY}&language=en-US"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("genres", [])
    except requests.RequestException:
        return None


def get_random_movie(genre_id=None, keyword=None):
    """
    Fetches a random movie, its providers, trailer, and top-billed cast.
    """
    max_pages_to_try = 5
    discover_url = f"{BASE_URL}/discover/movie?api_key={API_KEY}"
    discover_url += "&language=en-US&sort_by=popularity.desc"
    discover_url += "&watch_region=US"

    if keyword:
        search_url = (
            f"{BASE_URL}/search/keyword?api_key={API_KEY}&query={keyword}"
        )
        search_response = requests.get(search_url)
        if search_response.status_code == 200:
            results = search_response.json().get("results", [])
            if results:
                keyword_ids = [str(k["id"]) for k in results[:5]]
                keyword_param = "|".join(keyword_ids)
                discover_url += f"&with_keywords={keyword_param}"
            else:
                return None, None, None, None, f"Keyword '{keyword}' not found."
    else:
        discover_url += "&with_watch_monetization_types=flatrate"
        if genre_id:
            discover_url += f"&with_genres={genre_id}"

    # --- UPDATED: Search pages sequentially instead of randomly ---
    for page_num in range(1, max_pages_to_try + 1):
        page_url = discover_url + f"&page={page_num}"
        try:
            response = requests.get(page_url)
            response.raise_for_status()
            movies = response.json().get("results", [])

            # Get a list of all valid movies on the current page
            valid_movies_on_page = []
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
                    valid_movies_on_page.append((movie_data, available_providers))

            # If we found any valid movies, pick one and get its details
            if valid_movies_on_page:
                movie_data, available_providers = random.choice(valid_movies_on_page)
                movie_id = movie_data["id"]

                videos_url = f"{BASE_URL}/movie/{movie_id}/videos?api_key={API_KEY}"
                videos_response = requests.get(videos_url)
                trailer_key = None
                if videos_response.status_code == 200:
                    videos_data = videos_response.json().get("results", [])
                    for video in videos_data:
                        if video["type"] == "Trailer" and video["site"] == "YouTube":
                            trailer_key = video["key"]
                            break
                
                credits_url = f"{BASE_URL}/movie/{movie_id}/credits?api_key={API_KEY}"
                credits_response = requests.get(credits_url)
                cast = []
                if credits_response.status_code == 200:
                    credits_data = credits_response.json().get("cast", [])
                    cast = [
                        actor for actor in credits_data if actor.get("profile_path")
                    ][:3]

                return movie_data, available_providers, trailer_key, cast, None

        except requests.RequestException:
            # If an API call fails, try the next page
            continue

    return None, None, None, None, None


@app.route("/")
def index():
    """Renders the main page with genre options."""
    genres = get_genres()
    return render_template("index.html", genres=genres)


@app.route("/select", methods=["POST"])
def select_movie():
    """Handles the user's movie selection and displays a result."""
    movie, providers, trailer_key, cast, error = None, None, None, None, None
    selection_type = request.form.get("selection_type")

    if selection_type == "random":
        movie, providers, trailer_key, cast, error = get_random_movie()
    elif selection_type == "genre":
        genre_id = request.form.get("genre")
        movie, providers, trailer_key, cast, error = get_random_movie(genre_id=genre_id)
    elif selection_type == "keyword":
        keyword = request.form.get("keyword")
        if keyword:
            movie, providers, trailer_key, cast, error = get_random_movie(keyword=keyword)
        else:
            error = "Please enter a keyword."

    if not movie and not error:
        error = "Couldn't find a movie with that criteria. Please try again."

    return render_template(
        "movie.html",
        movie=movie,
        providers=providers,
        trailer_key=trailer_key,
        cast=cast,
        logo_base_url=LOGO_BASE_URL,
        profile_base_url=PROFILE_BASE_URL,
        error=error,
    )