from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
import requests
import os
from config import Config
from extensions import db, login_manager
from sqlalchemy import or_
from models import User, Movie, Review, MovieList, Message, APICache, SearchHistory
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager.init_app(app)

# --- REQUESTS SESSION SETUP ---
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_tmdb_session():
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

tmdb_session = get_tmdb_session()

def fetch_tmdb_data(url):
    """
    Fetches data from TMDB API with caching.
    1. Checks local DB for cached response.
    2. If not found, fetches from API and saves to DB.
    3. Handles errors gracefully.
    """
    # Check Cache First
    cached_data = APICache.query.filter_by(url=url).first()
    if cached_data:
        import json
        try:
            return json.loads(cached_data.response_json)
        except json.JSONDecodeError:
            pass # Invalid cache, fetch fresh
            
    # Fetch Fresh
    try:
        response = tmdb_session.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Save to Cache
            import json
            new_cache = APICache(url=url, response_json=json.dumps(data))
            db.session.add(new_cache)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Cache Save Error: {e}")
            return data
    except Exception as e:
        print(f"API Fetch Error: {e}")
        
    return None


# Helper to inject user list into templates
@app.context_processor
def inject_user_lists():
    if current_user.is_authenticated:
        user_lists = MovieList.query.filter_by(user_id=current_user.id).all()
        user_movies = Movie.query.filter_by(user_id=current_user.id).all()
        user_items = set()
        for m in user_movies:
            if m.tmdb_id and m.media_type:
                user_items.add((m.tmdb_id, m.media_type))
        return dict(user_lists=user_lists,user_items=user_items)
    return dict(user_lists=[], user_items=set())

# --- ROUTES ---
@app.route('/')
def index():
    # Fetch trending/now playing movies for the home page
    api_key = app.config['TMDB_API_KEY']
    url = f"https://api.themoviedb.org/3/movie/now_playing?api_key={api_key}&language=en-US&page=1"
    
    trending_movies = []
    
    trending_movies = []
    
    # Use cached helper
    data = fetch_tmdb_data(url)
    if data:
        trending_movies = data.get('results', [])[:12]
    else:
        print("Error fetching trending movies or no data returned.")

    return render_template('index.html', trending_movies=trending_movies)

import concurrent.futures

@app.route('/home')
@login_required
def home():
    api_key = app.config['TMDB_API_KEY']
    
    # --- 1. Prepare Target URLs ---
    urls_map = {} # {url: type_key}
    
    # Recommendations
    recommendation_title = "Recommended for You"
    last_search = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).first()
    rec_url = None
    if last_search:
        recommendation_title = "Recommended movies"
        rec_url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={last_search.search_term}&language=en-US"
        urls_map[rec_url] = 'recommendations'
    
    # Popular
    popular_url = f"https://api.themoviedb.org/3/movie/popular?api_key={api_key}&language=en-US&page=1"
    urls_map[popular_url] = 'popular'
    
    # Requested Genres: Action, Comedy, Horror
    genres = [
        {'id': 28, 'name': 'Action'},
        {'id': 35, 'name': 'Comedy'},
        {'id': 27, 'name': 'Horror'}
    ]
    genre_urls = []
    for g in genres:
        g_url = f"https://api.themoviedb.org/3/discover/movie?api_key={api_key}&with_genres={g['id']}&sort_by=popularity.desc&page=1&language=en-US"
        urls_map[g_url] = f"genre_{g['id']}"
        genre_urls.append((g, g_url))

    # --- 2. Parallel Fetching (Thread Safe) ---
    fetched_results = {} # {url: json_data}
    urls_to_network_fetch = []

    # Check Cache first (Main Thread)
    for url in urls_map.keys():
        if not url: continue
        cached = APICache.query.filter_by(url=url).first()
        if cached:
            try:
                import json
                fetched_results[url] = json.loads(cached.response_json)
            except:
                urls_to_network_fetch.append(url)
        else:
            urls_to_network_fetch.append(url)

    def fetch_task(url):
        try:
            # tmdb_session is thread-safe for .get()
            resp = tmdb_session.get(url, timeout=5)
            if resp.status_code == 200:
                return url, resp.json()
        except Exception as e:
            print(f"Fetch Error {url}: {e}")
        return url, None

    if urls_to_network_fetch:
        print(f"Parallel fetching {len(urls_to_network_fetch)} URLs...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(fetch_task, u): u for u in urls_to_network_fetch}
            for future in concurrent.futures.as_completed(future_to_url):
                url, data = future.result()
                if data:
                    fetched_results[url] = data
                    # Update cache in MAIN thread later or carefully here?
                    # Safer to just store in dict and update DB in main thread after executor.
    
    # Update Cache (Main Thread)
    import json
    new_entries = 0
    for url, data in fetched_results.items():
        if url in urls_to_network_fetch:
            # Only save if we actually fetched it fresh
            existing = APICache.query.filter_by(url=url).first()
            if not existing:
                db.session.add(APICache(url=url, response_json=json.dumps(data)))
                new_entries += 1
    
    if new_entries > 0:
        try:
            db.session.commit()
            print(f"Cached {new_entries} new responses.")
        except Exception as e:
            db.session.rollback()
            print(f"Cache Commit Error: {e}")

    # --- 3. Assemble Data ---
    recommended_movies = fetched_results.get(rec_url, {}).get('results', [])[:10] if rec_url else []
    popular_movies = fetched_results.get(popular_url, {}).get('results', [])[:10]
    
    # Static Fallback Movies (Used if TMDB is offline)
    # These act as a "starter pack" so the page is never empty
    STATIC_MOVIES = [
        {'id': 550, 'title': 'Fight Club', 'poster_path': '/pB8BM79vS6vMvMjeBhCHv6bqtBD.jpg'},
        {'id': 27205, 'title': 'Inception', 'poster_path': '/o0I0Bh0CDXmIOf9YvDY5pzkpYvC.jpg'},
        {'id': 157336, 'title': 'Interstellar', 'poster_path': '/gEU2QniE6EzuH6vCU2oEfQvHPH1.jpg'},
        {'id': 155, 'title': 'The Dark Knight', 'poster_path': '/qJ2tW6WMUDp9QmSbmvQYtG9T0lj.jpg'}
    ]

    # Mirror Fallback for Popular if API failed
    if not popular_movies:
        cached_pop = APICache.query.filter(APICache.url.like('%popular%')).first()
        if cached_pop:
            try:
                import json
                popular_movies = json.loads(cached_pop.response_json).get('results', [])[:10]
            except: pass
        if not popular_movies:
            popular_movies = STATIC_MOVIES

    genre_lists = []
    for g, g_url in genre_urls:
        movies = fetched_results.get(g_url, {}).get('results', [])[:10]
        # Fallback to cache
        if not movies:
             cached_g = APICache.query.filter(APICache.url.like(f"%with_genres={g['id']}%")).first()
             if cached_g:
                 try:
                     import json
                     movies = json.loads(cached_g.response_json).get('results', [])[:10]
                 except: pass
        
        # Static Fallback for specific genres if both API and Cache fail
        if not movies:
            if g['name'] == 'Action':
                movies = [{'id': 299534, 'title': 'Avengers: Endgame', 'poster_path': '/or06vSqzZkaunvunvSj97AI6r90.jpg'}]
            elif g['name'] == 'Comedy':
                movies = [{'id': 49013, 'title': 'Cars 2', 'poster_path': '/4X9U7vGg5YqJpYInInz7nS5ZcE1.jpg'}]
            elif g['name'] == 'Horror':
                movies = [{'id': 135397, 'title': 'Jurassic World', 'poster_path': '/muS9Uf96T96YvDY5pzkpYvC.jpg'}]

        if movies:
            genre_lists.append({'title': f"{g['name']} Movies", 'movies': movies})

    # Recommended Fallback
    if not recommended_movies:
        recommended_movies = STATIC_MOVIES[1:4]

    return render_template('home.html', 
                           recommended_movies=recommended_movies, 
                           recommendation_title=recommendation_title,
                           popular_movies=popular_movies,
                           genre_lists=genre_lists)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'])
        new_user = User(username=request.form['username'], password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        
        # Create default list
        default_list = MovieList(name="Watchlist", description="My main collection", user_id=new_user.id)
        db.session.add(default_list)
        db.session.commit()
        
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        new_username = request.form.get('username')
        avatar_file = request.files.get('avatar')
        
        # Update Username
        if new_username and new_username != current_user.username:
            existing_user = User.query.filter_by(username=new_username).first()
            if existing_user:
                flash('Username already taken.', 'error')
                return redirect(url_for('edit_profile'))
            current_user.username = new_username
            
        # Update Avatar
        if avatar_file and avatar_file.filename != '':
            filename = secure_filename(avatar_file.filename)
            # Ensure upload folder exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            # Save file
            # Rename file to user_id_filename to avoid collision
            new_filename = f"{current_user.id}_{filename}"
            avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            avatar_file.save(avatar_path)
            
            # Save relative path to DB
            current_user.avatar = f"uploads/avatars/{new_filename}"
            
        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile', username=current_user.username))
        except Exception as e:
            db.session.rollback()
            print(f"Update Error: {e}")
            flash('An error occurred while updating profile.', 'error')
            
    return render_template('edit_profile.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Show movies from "Watchlist" or all movies?
    # For now, let's just show all movies owned by user, or valid lists.
    # Group by lists?
    # Simple view: Show all lists.
    lists = MovieList.query.filter_by(user_id=current_user.id).all()
    # Also get pending messages count could go here if needed
    return render_template('dashboard.html', lists=lists)

@app.route('/profile/<string:username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # Calculate stats
    lists_count = MovieList.query.filter_by(user_id=user.id).count()
    reviews_count = Review.query.filter_by(user_id=user.id).count()
    
    # Get all movies from all lists to count unique movies
    user_lists = MovieList.query.filter_by(user_id=user.id).all()
    list_ids = [l.id for l in user_lists]
    movies_count = Movie.query.filter(Movie.list_id.in_(list_ids)).count() if list_ids else 0
    
    # Followers / Following counts
    followers_count = user.followers.count()
    following_count = user.followed.count()
    
    return render_template('profile.html', user=user, lists_count=lists_count, reviews_count=reviews_count, movies_count=movies_count, lists=user_lists, followers_count=followers_count, following_count=following_count)

@app.route('/list/<int:list_id>')
@login_required
def view_list(list_id):
    movie_list = MovieList.query.get_or_404(list_id)
    if movie_list.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('dashboard'))
    return render_template('list_view.html', movie_list=movie_list)

@app.route('/create_list', methods=['POST'])
@login_required
def create_list():
    name = request.form.get('name')
    description = request.form.get('description')
    cover_url = request.form.get('cover_url') # Custom/External Image URL
    
    # Handle File Upload
    if 'cover_file' in request.files:
        file = request.files['cover_file']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # Ensure upload directory exists
            upload_dir = os.path.join(app.root_path, 'static', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file
            # Use timestamp to prevent name collisions
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            save_name = f"{timestamp}_{filename}"
            file.save(os.path.join(upload_dir, save_name))
            
            # Update cover_url to point to local file
            cover_url = url_for('static', filename=f'uploads/{save_name}')
    
    new_list = MovieList(name=name, description=description, cover_url=cover_url, user_id=current_user.id)
    db.session.add(new_list)
    db.session.commit()
    flash('New list created.', 'success')
    return redirect(url_for('profile', username=current_user.username))

@app.route('/search', methods=['GET', 'POST'])
def search():
    movies = []
    tv_shows = []
    people = []
    query = request.form.get('query') or request.args.get('query')
    
    if query:
        # Save Search History
        if current_user.is_authenticated:
            new_search = SearchHistory(user_id=current_user.id, search_term=query)
            db.session.add(new_search)
            db.session.commit()

        api_key = app.config['TMDB_API_KEY']
        movie_url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}"
        tv_url = f"https://api.themoviedb.org/3/search/tv?api_key={api_key}&query={query}"
        
        # 1. Check Cache in Main Thread
        urls_map = {movie_url: 'movie', tv_url: 'tv'}
        fetched_results = {}
        urls_to_network_fetch = []
        
        for url in urls_map.keys():
            cached = APICache.query.filter_by(url=url).first()
            if cached:
                try:
                    import json
                    fetched_results[url] = json.loads(cached.response_json)
                except:
                    urls_to_network_fetch.append(url)
            else:
                urls_to_network_fetch.append(url)

        # 2. Local People Search (Main Thread)
        user_results = User.query.filter(User.username.ilike(f'%{query}%')).all()
        people = [u for u in user_results if not current_user.is_authenticated or u.id != current_user.id]

        # 3. Parallel Fetching for Missing URLs (No DB access here)
        def fetch_api_task(url):
            try:
                resp = tmdb_session.get(url, timeout=5)
                if resp.status_code == 200:
                    return url, resp.json()
            except Exception as e:
                print(f"Search Fetch Error {url}: {e}")
            return url, None

        if urls_to_network_fetch:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future_to_url = {executor.submit(fetch_api_task, u): u for u in urls_to_network_fetch}
                for future in concurrent.futures.as_completed(future_to_url):
                    url, data = future.result()
                    if data:
                        fetched_results[url] = data

        # 4. Update Cache in Main Thread
        import json
        new_entries = 0
        for url, data in fetched_results.items():
            if url in urls_to_network_fetch:
                existing = APICache.query.filter_by(url=url).first()
                if not existing:
                    db.session.add(APICache(url=url, response_json=json.dumps(data)))
                    new_entries += 1
        
        if new_entries > 0:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Search Cache Commit Error: {e}")

        # 5. Assemble Results
        movie_data = fetched_results.get(movie_url)
        tv_data = fetched_results.get(tv_url)
        if movie_data:
            for item in movie_data.get('results', []):
                movies.append({
                    'id': item.get('id'),
                    'title': item.get('title'),
                    'poster_path': item.get('poster_path'),
                    'media_type': 'movie',
                    'release_date': item.get('release_date', '')
                })
        
        if tv_data:
            for item in tv_data.get('results', []):
                tv_shows.append({
                    'id': item.get('id'),
                    'title': item.get('name'),
                    'poster_path': item.get('poster_path'),
                    'media_type': 'tv',
                    'release_date': item.get('first_air_date', '')
                })

    # Fetch trending for initial display
    trending_movies = []
    if not query:
        api_key = app.config['TMDB_API_KEY']
        url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={api_key}&language=en-US"
        data = fetch_tmdb_data(url)
        if data:
            trending_movies = data.get('results', [])[:10]

    return render_template('search.html', 
                          movies=movies, 
                          tv_shows=tv_shows, 
                          people=people, 
                          query=query, 
                          trending_movies=trending_movies)
    
@app.route('/add', methods=['POST'])
@login_required
def add():
    title = request.form.get('title')
    poster = request.form.get('poster')
    tmdb_id = request.form.get('tmdb_id')
    list_id = request.form.get('list_id') # User selects list
    media_type = request.form.get('media_type', 'movie')
    
    # Bug fix: Ensure poster path logic
    if poster:
        poster = poster.strip()
        
    if poster == 'None' or not poster:
        poster = None
        
    # Get user's default list if not specified
    if not list_id:
        default_list = MovieList.query.filter_by(user_id=current_user.id, name="Watchlist").first()
        if not default_list:
             # Fallback create if missing
             default_list = MovieList(name="Watchlist", user_id=current_user.id)
             db.session.add(default_list)
             db.session.commit()
        list_id = default_list.id

    # Check existence in THIS list
    existing_movie = Movie.query.filter_by(list_id=list_id, title=title).first()
    if existing_movie:
        flash('Movie already in this list!', 'error')
        return redirect(url_for('view_list', list_id=list_id))
    
    new_movie = Movie(title=title, poster=poster, tmdb_id=tmdb_id, user_id=current_user.id, list_id=list_id, media_type=media_type)
    db.session.add(new_movie)
    db.session.commit()
    flash('Movie added to collection.', 'success')
    return redirect(url_for('view_list', list_id=list_id))

@app.route('/movie/<int:tmdb_id>')
def movie_details(tmdb_id):
    api_key = app.config['TMDB_API_KEY']
    media_type = request.args.get('media_type', 'movie') # Get type from query param
    
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={api_key}&append_to_response=credits"
    
    details = {}
    data = fetch_tmdb_data(url)
    
    if data:
        details = data
        # Normalization for template (TV shows use 'name', Movies use 'title')
        if media_type == 'tv':
            details['title'] = details.get('name')
            details['release_date'] = details.get('first_air_date')
            details['runtime'] = details.get('episode_run_time', [0])[0] if details.get('episode_run_time') else 0
    else:
        flash('Unable to load movie details. Please check your connection.', 'error')
        return redirect(url_for('dashboard'))
            
    # Check if user has this movie/show in their list
    user_movie = None
    if current_user.is_authenticated:
        # Strict check with media_type to prevent ID collision
        user_movie = Movie.query.filter_by(tmdb_id=tmdb_id, media_type=media_type, user_id=current_user.id).first()
        
    # Get local reviews
    local_reviews = []
    
    # Better review fetching: Find all local movie entries with this TMDB ID AND media_type
    all_instances = Movie.query.filter_by(tmdb_id=tmdb_id, media_type=media_type).all()
    instance_ids = [m.id for m in all_instances]
    local_reviews = Review.query.filter(Review.movie_id.in_(instance_ids)).all() if instance_ids else []

    return render_template('movie_details.html', details=details, user_movie=user_movie, local_reviews=local_reviews, media_type=media_type)

@app.route('/review/<int:movie_id>', methods=['GET', 'POST'])
@login_required
def review(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    if movie.user_id != current_user.id:
        flash('You can only review movies in your own collection.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        rating = request.form.get('rating')
        content = request.form.get('content')
        
        new_review = Review(rating=rating, content=content, movie_id=movie.id, user_id=current_user.id)
        db.session.add(new_review)
        db.session.commit()
        flash('Review logged successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('review.html', movie=movie)

@app.route('/inbox')
@login_required
def inbox():
    # Find unique users the current user has exchanged messages with
    sent_recipient_ids = [msg.recipient_id for msg in Message.query.filter_by(sender_id=current_user.id).all()]
    received_sender_ids = [msg.sender_id for msg in Message.query.filter_by(recipient_id=current_user.id).all()]
    
    unique_user_ids = set(sent_recipient_ids + received_sender_ids)
    
    conversations = []
    for uid in unique_user_ids:
        user = User.query.get(uid)
        if user:
            conversations.append(user)
            
    return render_template('messages.html', conversations=conversations)

@app.route('/chat/<string:username>', methods=['GET', 'POST'])
@login_required
def chat(username):
    other_user = User.query.filter_by(username=username).first_or_404()
    
    if request.method == 'POST':
        body = request.form.get('body')
        if body:
            msg = Message(sender_id=current_user.id, recipient_id=other_user.id, body=body, is_read=False)
            db.session.add(msg)
            db.session.commit()
            return redirect(url_for('chat', username=username))
            
    # Get conversation history
    messages = Message.query.filter(
        or_(
            (Message.sender_id == current_user.id) & (Message.recipient_id == other_user.id),
            (Message.sender_id == other_user.id) & (Message.recipient_id == current_user.id)
        )
    ).order_by(Message.timestamp.asc()).all()
    
    return render_template('chat.html', other_user=other_user, messages=messages)

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    # Keep this for the "New Message" modal in inbox
    recipient_name = request.form.get('recipient')
    body = request.form.get('body')
    
    recipient = User.query.filter_by(username=recipient_name).first()
    if not recipient:
        flash('User not found!', 'error')
        return redirect(url_for('inbox'))
        
    new_msg = Message(sender_id=current_user.id, recipient_id=recipient.id, body=body)
    db.session.add(new_msg)
    db.session.commit()
    
    return redirect(url_for('chat', username=recipient.username))

@app.route('/compare/<string:username>')
@login_required
def compare_taste(username):
    target_user = User.query.filter_by(username=username).first_or_404()
    
    if target_user.id == current_user.id:
        flash("You are always 100% compatible with yourself!", "success")
        return redirect(url_for('dashboard'))

    # Fetch all reviews for both users, joined with Movie to get TMDB ID and Type
    my_reviews = db.session.query(Review, Movie).join(Movie).filter(Review.user_id == current_user.id).all()
    their_reviews = db.session.query(Review, Movie).join(Movie).filter(Review.user_id == target_user.id).all()
    
    # Map (tmdb_id, media_type) -> {rating, movie_obj}
    my_data = {}
    for r, m in my_reviews:
        if m.tmdb_id: # Only count entries with valid TMDB IDs
            key = (m.tmdb_id, m.media_type)
            my_data[key] = {'rating': r.rating, 'movie': m}

    their_data = {}
    for r, m in their_reviews:
        if m.tmdb_id:
            key = (m.tmdb_id, m.media_type)
            their_data[key] = {'rating': r.rating, 'movie': m}
    
    # Intersection (Movies both have rated)
    common_keys = set(my_data.keys()) & set(their_data.keys())
    
    comparison_data = []
    total_diff = 0
    max_possible_diff = len(common_keys) * 9
    
    # Recommendations: Things they like (>=8) that I haven't rated
    recommendations = []
    for key, data in their_data.items():
        if key not in my_data and data['rating'] >= 8:
            recommendations.append(data['movie'])
    
    # Limit recommendations to 3
    recommendations = recommendations[:3]

    for key in common_keys:
        my_rating = my_data[key]['rating']
        their_rating = their_data[key]['rating']
        diff = abs(my_rating - their_rating)
        total_diff += diff
        
        # Determine Category
        category = 'Normal'
        if my_rating >= 8 and their_rating >= 8:
            category = 'Shared Love'
        elif my_rating <= 4 and their_rating <= 4:
            category = 'Shared Hate'
        elif diff >= 4:
            category = 'Debate'
            
        comparison_data.append({
            'movie': my_data[key]['movie'], # Use my copy of movie obj for display
            'my_rating': my_rating,
            'their_rating': their_rating,
            'diff': diff,
            'category': category
        })
        
    # Calculate Score
    if not common_keys:
        score = 0 
        badge = "Strangers"
        description = "You haven't watched any of the same movies yet!"
    else:
        raw_score = 100 - ((total_diff / max_possible_diff) * 100)
        score = int(raw_score)
        
        if score >= 90:
            badge = "Soulmates"
            description = "It's like you share the same brain! Cinematic destiny."
        elif score >= 70:
            badge = "Besties"
            description = "Great minds think alike. You trust each other's taste."
        elif score >= 50:
            badge = "Casual Friends"
            description = "You agree on the big stuff, but argue about the details."
        elif score >= 30:
            badge = "Frenemies"
            description = "You respect each other, but your tastes are wildly different."
        else:
            badge = "Rivals"
            description = "Total opposites. If they hate it, you'll probably love it."

    return render_template('compare.html', 
                           target_user=target_user, 
                           score=score, 
                           badge=badge, 
                           description=description,
                           comparison_data=comparison_data,
                           common_count=len(common_keys),
                           recommendations=recommendations)

@app.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('User {} not found.'.format(username), 'error')
        return redirect(url_for('index'))
    if user == current_user:
        flash('You cannot follow yourself!', 'error')
        return redirect(url_for('profile', username=username))
    current_user.follow(user)
    db.session.commit()
    flash('You are now following {}!'.format(username), 'success')
    return redirect(url_for('profile', username=username))

@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('User {} not found.'.format(username), 'error')
        return redirect(url_for('index'))
    if user == current_user:
        flash('You cannot unfollow yourself!', 'error')
        return redirect(url_for('profile', username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash('You have unfollowed {}.'.format(username), 'success')
    return redirect(url_for('profile', username=username))

@app.route('/profile/<username>/followers')
def followers_list(username):
    user = User.query.filter_by(username=username).first_or_404()
    users = user.followers.all()
    return render_template('social_list.html', user=user, title="Followers", users=users)

@app.route('/profile/<username>/following')
def following_list(username):
    user = User.query.filter_by(username=username).first_or_404()
    users = user.followed.all()
    return render_template('social_list.html', user=user, title="Following", users=users)

@app.route('/friends', methods=['GET', 'POST'])
@login_required
def friends():
    # Handle user search
    search_query = request.args.get('q')
    search_results = []
    if search_query:
        search_results = User.query.filter(User.username.ilike(f'%{search_query}%')).all()
        # Filter out current user from results
        search_results = [u for u in search_results if u.id != current_user.id]

    # Get lists
    following = current_user.followed.all()
    followers = current_user.followers.all()
    
    return render_template('friends.html', 
                           following=following, 
                           followers=followers,
                           search_results=search_results,
                           search_query=search_query)

@app.route('/api/search-data')
def search_data():
    if not current_user.is_authenticated:
        return {'history': [], 'trending': []}
        
    # 1. Get Search History (Last 5)
    history = SearchHistory.query.filter_by(user_id=current_user.id)\
        .order_by(SearchHistory.timestamp.desc())\
        .limit(5).all()
        
    history_data = [{'term': h.search_term} for h in history]
    
    # 2. Get Trending Movies (from TMDB)
    api_key = app.config['TMDB_API_KEY']
    url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={api_key}"
    trending_data = []
    
    data = fetch_tmdb_data(url)
    if data:
        results = data.get('results', [])[:5]
        for movie in results:
            trending_data.append({
                'id': movie.get('id'),
                'title': movie.get('title'),
                'poster_path': movie.get('poster_path'),
                'media_type': 'movie'
            })
            
    return {'history': history_data, 'trending': trending_data}

@app.route('/api/clear-search-history', methods=['POST'])
@login_required
def clear_search_history():
    try:
        SearchHistory.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return {'status': 'success'}, 200
    except Exception as e:
        db.session.rollback()
        print(f"Clear History Error: {e}")
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
