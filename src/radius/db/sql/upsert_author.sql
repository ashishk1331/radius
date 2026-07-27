INSERT INTO authors (id, handle, display_name, avatar)
VALUES (?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    handle = excluded.handle,
    display_name = excluded.display_name;