import re
from app.keygen import generate_key


KEY_PATTERN = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def test_generate_key_matches_format():
    key = generate_key()
    assert KEY_PATTERN.match(key), f"Chave fora do formato: {key}"


def test_generate_key_uses_only_uppercase_and_digits():
    key = generate_key()
    raw = key.replace("-", "")
    assert all(c.isupper() or c.isdigit() for c in raw)


def test_generate_key_returns_unique_keys():
    keys = {generate_key() for _ in range(1000)}
    assert len(keys) == 1000, "Geração de 1000 chaves produziu duplicatas"
