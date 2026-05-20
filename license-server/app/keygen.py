import secrets

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def generate_key() -> str:
    chars = [secrets.choice(ALPHABET) for _ in range(16)]
    groups = ["".join(chars[i:i + 4]) for i in range(0, 16, 4)]
    return "-".join(groups)
