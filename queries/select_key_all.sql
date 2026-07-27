SELECT 
    id, 
    client_name, 
    created_at, 
    CASE 
        WHEN revoked_at IS NULL THEN 'ACTIVE'
        ELSE 'REVOKED'
    END AS status 
FROM api_keys;