from fastapi import Request

def mock_user(request: Request):
    return {
        "user_id": "mock-user-123",  # or str(uuid4()) for random
        "username": "dev_user",
        "email": "dev@example.com",
        "is_admin": True,
    }
