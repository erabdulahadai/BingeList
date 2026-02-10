from flask import Flask, render_template, request, redirect, url_for, flash

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
import requests
from config import Config
from extensions import db, login_manager, oauth
from sqlalchemy import or_
from models import User, Movie, Review, MovieList, Message
from datetime import datetime
import re

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager.init_app(app)
oauth.init_app(app)

# Configure Google OAuth
oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',  # This is only needed if using openid to fetch user info
    client_kwargs={'scope': 'openid email profile'},
)

# Helper to inject user list into templates
@app.context_processor
def inject_user_lists():
    if current_user.is_authenticated:
        user_lists = MovieList.query.filter_by(user_id=current_user.id).all()
        return dict(user_lists=user_lists)
    return dict(user_lists=[])

# --- ROUTES ---
@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
        
    # Fetch trending/now playing movies for the home page
    api_key = app.config['TMDB_API_KEY']
    url = f"https://api.themoviedb.org/3/movie/now_playing?api_key={api_key}&language=en-US&page=1"
    
    trending_movies = []
    try:
        response = requests.get(url)
        if response.status_code == 200:
            trending_movies = response.json().get('results', [])[:12] # Get top 12
    except Exception as e:
        print(f"Error fetching trending movies: {e}")

    return render_template('index.html', trending_movies=trending_movies)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Password Validation
        if len(password) < 8 or not re.search(r"[a-zA-Z]", password) or not re.search(r"\d", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            flash('Password must be at least 8 chars, include a letter, a number, and a special character.', 'error')
            return redirect(url_for('signup'))
            
        # Check if user exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or Email already exists.', 'error')
            return redirect(url_for('signup'))

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_pw)
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
        identifier = request.form['username'] # Can be username or email
        password = request.form['password']
        
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/login/google')
def google_login():
    mode = request.args.get('mode', 'login') # 'login' or 'signup'
    redirect_uri = url_for('google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri, state=mode)

@app.route('/login/google/callback')
def google_auth():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.parse_id_token(token, nonce=None)
    
    # In some flow, if parse_id_token fails or you want userinfo endpoint:
    # resp = oauth.google.get('userinfo')
    # user_info = resp.json()
    
    google_id = user_info.get('sub') # Google ID
    email = user_info.get('email')
    name = user_info.get('name') or email.split('@')[0]
    
    mode = request.args.get('state', 'login')
    
    user = User.query.filter((User.email == email) | (User.google_id == google_id)).first()
    
    if mode == 'login':
        if user:
            # Update google_id if missing
            if not user.google_id:
                user.google_id = google_id
                db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('User not found. Please sign up first.', 'error')
            return redirect(url_for('login'))
            
    elif mode == 'signup':
        if user:
            # If user exists, just log them in
            if not user.google_id:
                user.google_id = google_id
                db.session.commit()
            login_user(user)
            flash('Account already exists. Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        else:
            # Create new user
            import uuid
            random_password = str(uuid.uuid4())
            hashed_pw = generate_password_hash(random_password)
            
            # Ensure unique username
            base_username = name.replace(' ', '')
            username = base_username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{counter}"
                counter += 1
            
            new_user = User(username=username, email=email, google_id=google_id, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            
            # Create default list
            default_list = MovieList(name="Watchlist", description="My main collection", user_id=new_user.id)
            db.session.add(default_list)
            db.session.commit()
            
            login_user(new_user)
            return redirect(url_for('dashboard'))
            
    return redirect(url_for('login'))

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
    
    new_list = MovieList(name=name, description=description, cover_url=cover_url, user_id=current_user.id)
    db.session.add(new_list)
    db.session.commit()
    flash('New list created.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    movies = []
    search_type = 'movie' # Default
    if request.method == 'POST':
        query = request.form.get('query')
        search_type = request.form.get('search_type', 'movie')
        
        if query:
            api_key = app.config['TMDB_API_KEY']
            # Search endpoint depends on type
            url = f"https://api.themoviedb.org/3/search/{search_type}?api_key={api_key}&query={query}"
            response = requests.get(url)
            if response.status_code == 200:
                results = response.json().get('results', [])
                # Normalize results for template (TV shows have 'name' instead of 'title')
                for item in results:
                    movies.append({
                        'id': item.get('id'),
                        'title': item.get('title') if search_type == 'movie' else item.get('name'),
                        'poster_path': item.get('poster_path'),
                        'media_type': search_type
                    })
    
    return render_template('search.html', movies=movies, search_type=search_type)
    
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
    
    new_movie = Movie(title=title, poster=poster, tmdb_id=tmdb_id, user_id=current_user.id, list_id=list_id)
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
    response = requests.get(url)
    if response.status_code == 200:
        details = response.json()
        # Normalization for template (TV shows use 'name', Movies use 'title')
        if media_type == 'tv':
            details['title'] = details.get('name')
            details['release_date'] = details.get('first_air_date')
            details['runtime'] = details.get('episode_run_time', [0])[0] if details.get('episode_run_time') else 0
            # TV specific fields logic can be handled in template dynamically or normalized here
            
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

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
