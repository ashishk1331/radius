SELECT * FROM api_keys
WHERE client_name = ? AND revoked_at IS NULL;