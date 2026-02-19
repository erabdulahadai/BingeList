try:
    print("Importing app...")
    from app import app, db
    print("App imported.")
    
    print("Creating database tables...")
    with app.app_context():
        db.create_all()
    print("Tables created.")
    
    print("Success!")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
