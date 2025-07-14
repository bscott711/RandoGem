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
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w342" # For background

# TMDb Provider IDs for major US services
TARGET_PROVIDERS = {8, 9, 15, 337}  # Netflix, Prime, Hulu, Disney+
# --- End Configuration ---


def get_popular_movie_posters():
    """Fetches poster paths from the most popular movies for the background."""
    posters = []
    # Fetch first 3 pages to get 60 posters
    for page in range(1, 4):
        url = f"{BASE_URL}/movie/popular?api_key={API_KEY}&page={page}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            results = response.json().get("results", [])
            for movie in results:
                if movie.get("poster_path"):
                    posters.append(movie["poster_path"])
        except requests.RequestException:
            continue
    return posters


def get_genres():
    """Fetches the list of available movie genres from TMDb."""
    url = f"{BASE_URL}/genre/movie/list?api_key={API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("genres", [])
    except requests.RequestException:
        return None


def get_random_movie(filters):
    """
    Fetches a random movie based on a dictionary of filters.
    """
    max_pages_to_try = 10 # Increased for more complex queries
    discover_url = f"{BASE_URL}/discover/movie?api_key={API_KEY}"
    discover_url += "&language=en-US&sort_by=popularity.desc"
    discover_url += "&watch_region=US"

    # Apply all filters from the form
    for key, value in filters.items():
        if value: # Only add filter if a value was provided
            discover_url += f"&{key}={value}"

    for page_num in range(1, max_pages_to_try + 1):
        page_url = discover_url + f"&page={page_num}"
        try:
            response = requests.get(page_url)
            response.raise_for_status()
            movies = response.json().get("results", [])
            
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
            continue

    return None, None, None, None, None


@app.route("/")
def index():
    """Renders the main page with genre options and background posters."""
    genres = get_genres()
    posters = get_popular_movie_posters()
    return render_template("index.html", genres=genres, posters=posters, poster_base_url=POSTER_BASE_URL)


@app.route("/select", methods=["POST"])
def select_movie():
    """Handles the user's movie selection and displays a result."""
    
    # Build a dictionary of filters from the form data
    filters = {
        'with_genres': request.form.get('genres'),
        'primary_release_date.gte': request.form.get('release_date_from'),
        'primary_release_date.lte': request.form.get('release_date_to'),
        'vote_average.gte': float(request.form.get('user_score', 0)) / 10,
        'with_runtime.gte': request.form.get('runtime_min'),
        'with_runtime.lte': request.form.get('runtime_max'),
        'with_watch_monetization_types': 'flatrate'
    }

    movie, providers, trailer_key, cast, error = get_random_movie(filters)

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