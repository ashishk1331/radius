SELECT a.id, a.display_name, a.handle, a.avatar, COUNT(t.id) as number_of_saved_tweets 
FROM authors a
LEFT JOIN tweets t
ON t.author_id = a.id
GROUP BY a.handle
ORDER BY number_of_saved_tweets DESC;