import random

def generate_verification_code():
    return f"{random.randint(100000, 999999)}"
