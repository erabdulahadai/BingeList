from app import app
from extensions import db
from models import User, Movie, MovieList

def seed_titanic():
    with app.app_context():
        user = User.query.first()
        if not user:
            print("No user found! Please create an account first.")
            return

        movie_list = MovieList.query.filter_by(user_id=user.id).first()
        if not movie_list:
            print("No movie list found for user!")
            return

        # Check if already exists
        existing = Movie.query.filter_by(title="Titanic", user_id=user.id).first()
        if existing:
            print(f"Titanic is already in the collection of {user.username}!")
            return

        # Add Titanic
        print(f"Adding Titanic to {user.username}'s list '{movie_list.name}'...")
        titanic = Movie(
            title="Titanic",
            tmdb_id=597,
            poster="https://image.tmdb.org/t/p/w500/9xjZS2rlVxm8SFx8kPC3aIGCOYQ.jpg",
            media_type="movie",
            user_id=user.id,
            list_id=movie_list.id
        )
        db.session.add(titanic)
        db.session.commit()
        print("Successfully added Titanic to the database!")

if __name__ == "__main__":
    seed_titanic()
