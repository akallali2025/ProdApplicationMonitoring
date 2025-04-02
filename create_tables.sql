CREATE TABLE IF NOT EXISTS websites (
    website_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url                TEXT    NOT NULL UNIQUE,
    name               TEXT    NOT NULL DEFAULT '',
    active             INTEGER NOT NULL DEFAULT 1,
    total_emails_sent  INTEGER NOT NULL DEFAULT 0,
    last_tested        DATETIME DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS website_emails (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    website_id  INTEGER NOT NULL,
    email       TEXT NOT NULL,
    FOREIGN KEY (website_id) REFERENCES websites(website_id)
);

CREATE TABLE IF NOT EXISTS config (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    work_hours_start INTEGER NOT NULL DEFAULT 7,
    work_hours_end   INTEGER NOT NULL DEFAULT 17,  -- 5 pm in 24-hour format
    mute_all         INTEGER NOT NULL DEFAULT 0 
                     CHECK (mute_all IN (0, 1))
);
