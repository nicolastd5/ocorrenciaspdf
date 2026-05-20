from app.security import hash_password, verify_password

def test_hash_password_returns_non_plaintext():
    pw = "minha-senha-super-secreta"
    h = hash_password(pw)
    assert h != pw
    assert len(h) > 20

def test_verify_password_matches_hash():
    pw = "outra-senha-123"
    h = hash_password(pw)
    assert verify_password(pw, h) is True

def test_verify_password_rejects_wrong_password():
    h = hash_password("senha-original")
    assert verify_password("senha-errada", h) is False

def test_hash_password_produces_different_hash_each_time():
    pw = "mesma-senha"
    assert hash_password(pw) != hash_password(pw)


from app.security import generate_csrf_token, verify_csrf_token

def test_generate_csrf_token_is_non_empty_string():
    token = generate_csrf_token()
    assert isinstance(token, str)
    assert len(token) >= 32

def test_verify_csrf_token_accepts_matching_tokens():
    token = generate_csrf_token()
    assert verify_csrf_token(token, token) is True

def test_verify_csrf_token_rejects_mismatch():
    a = generate_csrf_token()
    b = generate_csrf_token()
    assert verify_csrf_token(a, b) is False

def test_verify_csrf_token_rejects_none_or_empty():
    token = generate_csrf_token()
    assert verify_csrf_token(token, None) is False
    assert verify_csrf_token(None, token) is False
    assert verify_csrf_token("", token) is False


from app.security import mask_key

def test_mask_key_keeps_first_four_chars():
    assert mask_key("A3F2-9K1P-XQ7M-BN4T") == "A3F2-***"

def test_mask_key_handles_short_input():
    assert mask_key("A3") == "***"
    assert mask_key("") == "***"
    assert mask_key(None) == "***"
