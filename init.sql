CREATE DATABASE IF NOT EXISTS jobnotifier;
USE jobnotifier;

-- Users registered via the Telegram bot
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    chat_id       BIGINT NOT NULL UNIQUE,
    username      VARCHAR(255),
    is_active     BOOLEAN DEFAULT TRUE,
    notify_interval_hours INT DEFAULT 6,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Per-user (or global) search configurations
CREATE TABLE IF NOT EXISTS search_configs (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    search_term   VARCHAR(255) NOT NULL,
    location      VARCHAR(255),
    is_remote     BOOLEAN DEFAULT FALSE,
    results_wanted INT DEFAULT 20,
    site_names    VARCHAR(255) DEFAULT 'linkedin,indeed,glassdoor',
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Every job posting ever scraped
CREATE TABLE IF NOT EXISTS jobs (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    job_id        VARCHAR(512) NOT NULL,
    site          VARCHAR(50)  NOT NULL,
    title         VARCHAR(512),
    company       VARCHAR(255),
    location      VARCHAR(255),
    is_remote     BOOLEAN,
    job_type      VARCHAR(100),
    salary_min    DECIMAL(10,2),
    salary_max    DECIMAL(10,2),
    currency      VARCHAR(10),
    description   TEXT,
    job_url       VARCHAR(1024),
    date_posted   DATE,
    scraped_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_job (job_id, site)
);

-- Audit log: which jobs were sent to which user and when
CREATE TABLE IF NOT EXISTS notifications (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    job_id        INT NOT NULL,
    sent_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (job_id)  REFERENCES jobs(id)  ON DELETE CASCADE,
    UNIQUE KEY uq_notification (user_id, job_id)
);