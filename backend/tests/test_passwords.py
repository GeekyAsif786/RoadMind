from app.core.passwords import hash_password, verify_password


def test_password_hash_is_not_plaintext():
    password = "TestPassword123!"
    password_hash = hash_password(password)

    assert password_hash != password


def test_correct_password_verifies():
    password = "TestPassword123!"
    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True


def test_wrong_password_does_not_verify():
    password = "TestPassword123!"
    password_hash = hash_password(password)

    assert verify_password("WrongPassword!", password_hash) is False


def test_same_password_gets_different_hashes():
    password = "TestPassword123!"

    hash_one = hash_password(password)
    hash_two = hash_password(password)

    assert hash_one != hash_two
