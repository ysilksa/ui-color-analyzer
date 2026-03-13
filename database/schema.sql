CREATE TABLE images (
    image_id UUID PRIMARY KEY,
    s3_key TEXT NOT NULL,
    palette JSONB,
    harmony_score FLOAT,
    contrast_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);