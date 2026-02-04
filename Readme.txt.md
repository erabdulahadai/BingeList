# BingeList - Movie Collection Manager

BingeList is a web application that helps users organize their movie watching experience. It allows you to create custom movie lists, search for movies using the TMDB API, track your watched movies, and even message other users.

## Features

-   **User Authentication**: Secure sign-up and login system.
-   **Movie Management**:
    -   Create multiple movie lists (e.g., "Watchlist", "Favorites").
    -   Search for movies using real-world data from TMDB.
    -   Add movies to specific functional lists.
    -   View details, cast, and reviews for movies.
-   **Social Features**:
    -   Write reviews for movies in your collection.
    -   Send and receive messages with other users.
-   **Dashboard**: A clear overview of your lists and collections.

## Tech Stack

-   **Backend**: Flask (Python)
-   **Database**: SQLite (via SQLAlchemy)
-   **Frontend**: HTML, CSS (Vanilla), Jinja2 Templates
-   **External API**: The Movie Database (TMDB) API

## Prerequisites

-   Python 3.8 or higher
-   Pip (Python Package Manager)

## Installation

1.  **Clone the repository** (or download the source code):
    ```bash
    git clone <repository-url>
    cd BingeList
    ```

2.  **Create a virtual environment** (recommended):
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Environment Variables**:
    By default, the application uses a default secret key and TMDB API key for development. For production or if you want to use your own keys, you can set the following environment variables:
    
    *   `SECRET_KEY`: Your Flask secret key.
    *   `DATABASE_URL`: Database connection string (defaults to `sqlite:///bingelist.db`).
    *   `TMDB_API_KEY`: Your API Key from [The Movie Database (TMDB)](https://www.themoviedb.org/documentation/api).

## Usage

1.  **Initialize the Database**:
    The application will automatically create the database tables (`bingelist.db`) on the first run if they don't exist.

2.  **Run the Application**:
    ```bash
    python app.py
    ```

3.  **Access the App**:
    Open your web browser and navigate to: `http://127.0.0.1:5000`

## Project Structure

-   `app.py`: Main application entry point and route definitions.
-   `models.py`: Database models (User, Movie, MovieList, Review, Message).
-   `extensions.py`: Flask extensions setup (SQLAlchemy, LoginManager).
-   `config.py`: Configuration settings.
-   `templates/`: HTML templates for the application pages.
-   `static/`: Static assets (CSS, JS, images).

## License

[MIT License](LICENSE)
