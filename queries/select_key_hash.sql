SELECT key_hash FROM api_keys
WHERE key_hash = ? and revoked_at IS NULL;