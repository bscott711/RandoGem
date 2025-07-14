import os
import random
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# Remember to set your TMDB API key as an environment variable
# named TMDB_API_KEY.
API_KEY = os.environ.get("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"


def get_genres():
    """Fetches the list of available movie genres from TMDb."""
    url = f"{BASE_URL}/genre/movie/list?api_key={API_KEY}&language=en-US"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    genres_data = response.json()
    return genres_data["genres"]


def get_random_movie(genre_id=None, keyword=None):
    """Fetches a random movie from TMDb."""
    url = f"{BASE_URL}/discover/movie?api_key={API_KEY}"
    url += "&language=en-US&sort_by=popularity.desc"
    url += f"&page={random.randint(1, 100)}"

    if genre_id:
        url += f"&with_genres={genre_id}"
    if keyword:
        # To use keywords, we first need to get the keyword ID
        search_url = f"{BASE_URL}/search/keyword?api_key={API_KEY}&query={keyword}"
        search_response = requests.get(search_url)
        if search_response.status_code == 200:
            results = search_response.json().get("results")
            if results:
                keyword_id = results[0]["id"]
                url += f"&with_keywords={keyword_id}"

    response = requests.get(url)
    if response.status_code != 200:
        return None

    movies = response.json().get("results", [])
    if not movies:
        return None

    return random.choice(movies)


@app.route("/")
def index():
    """Renders the main page with genre options."""
    genres = get_genres()
    return render_template("index.html", genres=genres)


@app.route("/select", methods=["POST"])
def select_movie():
    """Handles the user's movie selection and displays a result."""
    movie = None
    selection_type = request.form.get("selection_type")
    error = None

    if selection_type == "random":
        movie = get_random_movie()
    elif selection_type == "genre":
        genre_id = request.form.get("genre")
        movie = get_random_movie(genre_id=genre_id)
    elif selection_type == "keyword":
        keyword = request.form.get("keyword")
        if keyword:
            movie = get_random_movie(keyword=keyword)
        else:
            error = "Please enter a keyword."

    if not movie and not error:
        error = "Couldn't find a movie with that criteria. Please try again."

    return render_template(
        "movie.html", movie=movie, poster_base_url=POSTER_BASE_URL, error=error
    )
