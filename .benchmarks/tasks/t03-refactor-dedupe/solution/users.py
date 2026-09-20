def normalize_name(name):
    return " ".join(name.strip().lower().split())


def format_user(name):
    return "user:" + normalize_name(name)


def format_admin(name):
    return "admin:" + normalize_name(name)
