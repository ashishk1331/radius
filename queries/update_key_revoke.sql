UPDATE api_keys
SET revoked_at = CURRENT_TIMESTAMP
WHERE client_name = ? AND revoked_at IS NULL;