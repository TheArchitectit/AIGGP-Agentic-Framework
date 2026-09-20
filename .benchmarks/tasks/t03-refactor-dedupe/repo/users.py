def format_user(name):
    cleaned = name.strip().lower()
    cleaned = " ".join(cleaned.split())
    return "user:" + cleaned


def format_admin(name):
    cleaned = name.strip().lower()
    cleaned = " ".join(cleaned.split())
    return "admin:" + cleaned
