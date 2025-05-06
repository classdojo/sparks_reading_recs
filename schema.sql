-- DROP TABLE IF EXISTS Profiles; -- Removed to persist data
-- DROP TABLE IF EXISTS Books;    -- Removed to persist data
-- DROP TABLE IF EXISTS ReadBooks; -- Removed to persist data

CREATE TABLE IF NOT EXISTS Profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    avatar TEXT -- Path to avatar image, or placeholder
);

CREATE TABLE IF NOT EXISTS Books (
    id TEXT PRIMARY KEY, -- Google Books ID for uniqueness
    title TEXT NOT NULL,
    authors TEXT, -- Comma-separated string of authors
    thumbnail_url TEXT -- URL to the book's cover image
);

CREATE TABLE IF NOT EXISTS ReadBooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    book_id TEXT NOT NULL,
    read_date DATE, -- Optional: when the book was read
    rating INTEGER, -- Optional: user's rating (e.g., 1-5)
    FOREIGN KEY (profile_id) REFERENCES Profiles (id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES Books (id) ON DELETE CASCADE,
    UNIQUE (profile_id, book_id) -- A user can only read a specific book once in this log
);

-- We will define Books and ReadBooks tables later
/*
CREATE TABLE Books (
    id TEXT PRIMARY KEY, -- e.g., Google Books ID
    title TEXT NOT NULL,
    authors TEXT, -- Comma-separated string or normalize further
    thumbnail_url TEXT
);

CREATE TABLE ReadBooks (
    profile_id INTEGER NOT NULL,
    book_id TEXT NOT NULL,
    read_date DATE,
    rating INTEGER, -- e.g., 1-5 stars
    FOREIGN KEY (profile_id) REFERENCES Profiles (id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES Books (id) ON DELETE CASCADE,
    PRIMARY KEY (profile_id, book_id)
);
*/ 