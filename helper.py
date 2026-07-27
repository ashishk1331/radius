from rapidfuzz import fuzz


def fuzzy_score(content: str, query: str) -> float:
    if not content or not query:
        return 0.0
    return float(fuzz.partial_ratio(query.lower(), content.lower()))


def read_query(file_name: str) -> str:
    with open(f"queries/{file_name}.sql", "r") as file:
        return file.read()
