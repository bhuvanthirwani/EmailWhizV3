
from pymongo import MongoClient


client = MongoClient('mongodb+srv://shoaibthakur23:Shoaib@emailwhiz.ltjxh42.mongodb.net/')  # Replace with your MongoDB connection URI
db = client['EmailWhiz']  # Replace with your database name
users_collection = db['users']
jobs_collection = db['jobs']

def get_users_db(db_url):
    users_client = MongoClient(db_url)
    print("users_client: ", users_client) 
    return users_client['EmailWhiz']

def get_user_details(username):
    """
    Fetches user details from MongoDB for a given username.

    Args:
        username (str): The username of the user.

    Returns:
        dict: A dictionary containing user details if found.

    Raises:
        ValueError: If the user is not found in the database.
    """
    # Query MongoDB to find the user
    user = users_collection.find_one({"username": username})
    
    if not user:
        # Raise an error if the user is not found
        raise ValueError(f"User with username '{username}' not found.")
    
    # Construct the user data dictionary
    user_data = {
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "university": user.get("college"),
        "graduation_done": user.get("graduated_or_not", "").lower() != 'no',  # Graduation status
        "email": user.get("email"),
        "linkedin_url": user.get("linkedin_url"),
        "phone_number": user.get("phone_number"),
        "degree_name": user.get("degree_name"),
        "gemini_api_key": user.get("gemini_api_key"),
        "roles": user.get("roles"),
        "db_url": user.get("db_url"),
        "gmail_id": user.get("gmail_id"),
        "gmail_in_app_password": user.get("gmail_in_app_password"),
    }

    return user_data
