from flask import Flask, render_template, request, redirect, url_for, g
import requests # For making HTTP requests to Google Books API
import sqlite3 # For database operations
import datetime # For read_date

app = Flask(__name__)
DATABASE = 'sparky_recs.db' # Database file path

def get_db():
    """Connects to the specific database."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Access columns by name
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database again at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_sqlite_db():
    """Initializes the database and creates tables if they don't exist."""
    with app.app_context(): # Need app context to use get_db with g
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
    print("Initialized the SQLite database and created tables if they didn't exist.")

# Updated function to search books on Google Books API
def search_books_on_google(query_string):
    api_url = f'https://www.googleapis.com/books/v1/volumes?q={requests.utils.quote(query_string)}&maxResults=10'
    print(f"Querying Google Books API: {api_url}")
    books_found = []
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        for item in data.get('items', []):
            volume_info = item.get('volumeInfo', {})
            gbook_id = item.get('id', None)
            title = volume_info.get('title', 'No title available')
            authors = volume_info.get('authors', ['Unknown author'])
            thumbnail = volume_info.get('imageLinks', {}).get('smallThumbnail', None)
            if gbook_id:
                books_found.append({
                    'gbook_id': gbook_id,
                    'title': title,
                    'author': ", ".join(authors),
                    'thumbnail_url': thumbnail
                })
    except requests.exceptions.RequestException as e:
        print(f"Google Books API request failed: {e}")
        # Return error indication, could be a specific dict or raise exception
        return None # Or specific error structure
    except Exception as e:
        print(f"Error processing Google Books API response: {e}")
        return None
    return books_found

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/profile-select')
def profile_select_page():
    db = get_db()
    cur = db.execute('SELECT id, name, avatar FROM Profiles ORDER BY name')
    profiles_from_db = cur.fetchall()
    return render_template('profile_select.html', profiles=profiles_from_db)

@app.route('/new-user', methods=['GET', 'POST'])
def new_user_page():
    if request.method == 'POST':
        profile_name = request.form.get('profile_name', '').strip()
        if profile_name:
            db = get_db()
            try:
                # Using a placeholder avatar for now
                db.execute('INSERT INTO Profiles (name, avatar) VALUES (?, ?)',
                           (profile_name, 'default_avatar.png'))
                db.commit()
                return redirect(url_for('profile_select_page'))
            except sqlite3.IntegrityError: # Handles UNIQUE constraint violation for name
                return render_template('new_user.html', error=f"Profile name '{profile_name}' already exists.")
            except Exception as e:
                 print(f"Database error: {e}")
                 return render_template('new_user.html', error="An error occurred saving the profile.")
        else:
            return render_template('new_user.html', error="Profile name cannot be empty.")
    return render_template('new_user.html') # For GET requests

@app.route('/profile/<int:profile_id>', methods=['GET', 'POST'])
def profile_detail_page(profile_id):
    db = get_db()
    # Fetch profile details
    profile_cur = db.execute('SELECT id, name, avatar FROM Profiles WHERE id = ?', (profile_id,))
    profile = profile_cur.fetchone()
    if not profile:
        return "Profile not found", 404

    search_results = None
    if request.method == 'POST': # Book search form submitted
        book_search_query = request.form.get('book_search_query', '').strip()
        if book_search_query:
            search_results = search_books_on_google(book_search_query)
    
    # Fetch read books for this profile
    read_books_cur = db.execute('''
        SELECT b.id, b.title, b.authors, b.thumbnail_url, rb.read_date, rb.rating 
        FROM Books b JOIN ReadBooks rb ON b.id = rb.book_id 
        WHERE rb.profile_id = ? ORDER BY rb.read_date DESC, b.title
    ''', (profile_id,))
    read_books = read_books_cur.fetchall()

    return render_template('profile_detail.html', profile=profile, read_books=read_books, search_results=search_results)

@app.route('/profile/<int:profile_id>/add_book', methods=['POST'])
def add_book_to_profile(profile_id):
    db = get_db()
    # Ensure profile exists
    profile_exists = db.execute('SELECT id FROM Profiles WHERE id = ?', (profile_id,)).fetchone()
    if not profile_exists:
        return "Profile not found", 404

    gbook_id = request.form.get('gbook_id')
    title = request.form.get('title')
    authors = request.form.get('authors')
    thumbnail_url = request.form.get('thumbnail_url')

    if not gbook_id or not title:
        # Handle error: missing essential book info
        return redirect(url_for('profile_detail_page', profile_id=profile_id, error="Missing book information."))

    try:
        # Add book to Books table if it doesn't exist (IGNORE on conflict means if ID exists, do nothing)
        db.execute('INSERT OR IGNORE INTO Books (id, title, authors, thumbnail_url) VALUES (?, ?, ?, ?)',
                   (gbook_id, title, authors, thumbnail_url))
        
        # Add to ReadBooks
        # For now, using current date as read_date, no rating
        today_date = datetime.date.today().isoformat()
        db.execute('INSERT INTO ReadBooks (profile_id, book_id, read_date) VALUES (?, ?, ?)',
                   (profile_id, gbook_id, today_date))
        db.commit()
    except sqlite3.IntegrityError: # Handles UNIQUE constraint on (profile_id, book_id) in ReadBooks
        # User has already logged this book
        pass # Or redirect with a message: "Book already logged"
    except Exception as e:
        print(f"Error adding book to profile: {e}")
        db.rollback() # Rollback on error
        # Redirect with a generic error message
        return redirect(url_for('profile_detail_page', profile_id=profile_id, error="Error logging book."))

    return redirect(url_for('profile_detail_page', profile_id=profile_id))

@app.route('/recommendations')
def recommendations_page():
    profile_id = request.args.get('profile_id', type=int)
    if not profile_id:
        return "Profile ID is required for recommendations.", 400

    db = get_db()
    profile_cur = db.execute('SELECT id, name FROM Profiles WHERE id = ?', (profile_id,))
    profile = profile_cur.fetchone()
    if not profile:
        return "Profile not found for recommendations.", 404

    read_books_cur = db.execute('SELECT b.id as gbook_id, b.title, b.authors FROM Books b JOIN ReadBooks rb ON b.id = rb.book_id WHERE rb.profile_id = ? ORDER BY rb.read_date DESC LIMIT 5', (profile_id,))
    # Create a list of book objects that were read to easily check against later
    user_read_books_details = [{ "gbook_id": row['gbook_id'], "title": row['title'] } for row in read_books_cur.fetchall()]
    read_book_titles_for_search = [book['title'] for book in user_read_books_details]

    all_suggested_books_structured = [] # Will be list of dicts

    if not read_book_titles_for_search:
        display_recommendations = [{'message': "Log some books you've read to get personalized recommendations!"}]
        return render_template('recommendations.html', profile=profile, recommendations=display_recommendations)

    # Set to keep track of suggested book Google IDs to avoid duplicates from different searches
    suggested_gbook_ids = set(book['gbook_id'] for book in user_read_books_details)

    for r_title in read_book_titles_for_search:
        api_results = search_books_on_google(r_title) 
        if api_results:
            for book_data in api_results: # book_data is expected to be a dict from search_books_on_google
                gbook_id = book_data.get('gbook_id')
                title = book_data.get('title')
                author = book_data.get('author', 'N/A') # Default author if not present

                if gbook_id and gbook_id not in suggested_gbook_ids:
                    amazon_query = f"{title} {author}"
                    amazon_url = f"https://www.amazon.com/s?k={requests.utils.quote(amazon_query)}&i=stripbooks"
                    
                    all_suggested_books_structured.append({
                        'title': title,
                        'author': author,
                        'amazon_search_url': amazon_url,
                        'gbook_id': gbook_id # Store gbook_id to help avoid duplicates
                    })
                    suggested_gbook_ids.add(gbook_id)
    
    if not all_suggested_books_structured:
        display_recommendations = [{'message': f"Could not find new book recommendations based on the books '{profile.name}' has read. Try reading more varied books!"}]
    else:
        display_recommendations = all_suggested_books_structured[:15]

    return render_template('recommendations.html', profile=profile, recommendations=display_recommendations)

# Add g to Flask for app context
if __name__ == '__main__':
    init_sqlite_db() # Initialize DB when app starts
    app.run(debug=True) 