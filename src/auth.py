import hashlib

def generate_auth(action, user_id):
    # The salt string
    salt = "GN1al351"
    
    # Combine action, salt, and user_id
    combined_string = action + salt + str(user_id)
    
    # Generate the MD5 hash of the combined string
    auth = hashlib.md5(combined_string.encode('utf-8')).hexdigest()
    
    return auth

if __name__ == "__main__":
    action = "autoLoginUser"
    user_id = 0

    auth_value = generate_auth(action, user_id)
    print("Generated Auth:", auth_value)