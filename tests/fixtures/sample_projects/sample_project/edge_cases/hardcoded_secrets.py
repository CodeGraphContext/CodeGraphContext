def connect_to_service():
    password = "supersecret123"
    api_key = "AKIAIOSFODNN7EXAMPLE"
    secret_token = "ghp_16charactertoken"
    # Simulate usage
    print("Connecting with password:", password)
    print("Using API key:", api_key)
    print("Token:", secret_token)
    return True

def harmless_function():
    value = 42
    print("This function does not use secrets.")
    return value