from flask import Flask, request, jsonify, send_file, session
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
import uuid
import os
import json
from flask_cors import CORS, cross_origin
from functools import wraps
import copy
import time
import math
import traceback
import shlex
import requests
from datetime import datetime, timedelta
import pytz
from itertools import combinations
import google.generativeai as genai
from PyPDF2 import PdfReader
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
# Configure Flask session
app.config['SECRET_KEY'] = 'EmailWhiz'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# CORS(app, resources={r"/*": {"origins": ["*", "http://localhost:5173"]}}, supports_credentials=True)
# http://localhost:5173/
# CORS(app, resources={r"/api/*": {"origins": ["*", "http://localhost:5173"]}})
CORS(app, supports_credentials=True, origins=["*"])

# MongoDB setup (adjust URI as needed)
client = MongoClient('mongodb+srv://shoaibthakur23:Shoaib@emailwhiz.ltjxh42.mongodb.net/')
db = client['EmailWhiz']
users_collection = db['users']
apollo_apis_curl_collection = db['apollo_apis_curl']
apollo_emails_collection = db['apollo_emails']

# Media root for file storage
MEDIA_ROOT = 'media'

def get_user_details(username):
    """
    Fetches user details from MongoDB for a given username.
    """
    user = users_collection.find_one({"username": username})
    
    if not user:
        raise ValueError(f"User with username '{username}' not found.")
    
    user_data = {
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "university": user.get("college"),
        "graduation_done": user.get("graduated_or_not", "").lower() != 'no',
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

def get_users_db(db_url):
    users_client = MongoClient(db_url)
    return users_client['EmailWhiz']

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            text += page.extract_text()
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

def call_gemini_api(prompt, model):
    chat_session = model.start_chat(history=[])
    response = chat_session.send_message(prompt)
    return response

def parse_curl_command(curl_command):
    """
    Parse a curl command and return the equivalent Python request components.
    """
    tokens = shlex.split(curl_command)
    url = None
    headers = {}
    data = None

    for i, token in enumerate(tokens):
        if token == "curl":
            continue
        elif token.startswith("http"):
            url = token
        elif token == "-H":
            header = tokens[i + 1].split(": ", 1)
            if len(header) == 2:
                headers[header[0]] = header[1]
        elif token in ("--data-raw", "-d"):
            data = tokens[i + 1]

    return url, headers, data

def replace_value_by_key(json_string, key, new_value):
    """Replaces the value of a specific key in a JSON-like string."""
    start_index = json_string.index(f'"{key}":')

    if isinstance(new_value, str):
        end_index = json_string.find('"', start_index + len(f'"{key}":') + 1)
        new_value_str = f'"{new_value}"'
    elif isinstance(new_value, list):
        new_value_str = ''
        for i in range(len(new_value)):
            new_value_str += '"' + new_value[i] + '"'
            if i != len(new_value) - 1:
                new_value_str += ','
        new_value_str = f'[{new_value_str}]' 
        end_index = json_string.find(']', start_index + len(f'"{key}":') + 1)
    elif isinstance(new_value, int):
        end_index = json_string.find(',', start_index + len(f'"{key}":') + 1) - 1 
        new_value_str = str(new_value)
    else:
        raise ValueError("Unsupported value type")

    return json_string[:start_index + len(f'"{key}":')] + new_value_str + json_string[end_index+1:]

def update_email_history(username, receiver_email, subject, content, company, designation):
    """Update email history for a user."""
    user_dir = os.path.join(MEDIA_ROOT, username)
    os.makedirs(user_dir, exist_ok=True)
    
    history_file = os.path.join(user_dir, 'history.json')
    
    if os.path.exists(history_file):
        with open(history_file, 'r') as file:
            history_data = json.load(file)
    else:
        history_data = {"history": []}
    
    date = datetime.now().strftime('%Y-%m-%d')

    recipient_history = next((item for item in history_data["history"] if item["receiver_email"] == receiver_email), None)
    if recipient_history:
        recipient_history["emails"].append({
            "subject": subject, 
            "content": content, 
            "designation": designation,
            "date": date,
        })
    else:
        history_data["history"].append({
            "receiver_email": receiver_email,
            "company": company,
            "emails": [{
                "subject": subject, 
                "content": content, 
                "designation": designation, 
                "date": date,
            }]
        })
    
    with open(history_file, 'w') as file:
        json.dump(history_data, file, indent=4)

@app.route('/')
def home():
    return 'Hello, World!'


# MongoDB setup (adjust URI as needed)
# client = MongoClient('mongodb+srv://shoaibthakur23:Shoaib@emailwhiz.ltjxh42.mongodb.net/')
# db = client['EmailWhiz']
# users_collection = db['users']

@app.route('/register', methods=['POST'])
# @cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def register():
    data = request.get_json()
    required_fields = [
        "first_name", "last_name", "phone_number", "linkedin_url", "email", "graduated_or_not", "college", "degree_name", "gmail_id", "gmail_in_app_password", "gemini_api_key", "db_url", "username", "password"
    ]
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

    if users_collection.find_one({'username': data["username"]}):
        return jsonify({'error': 'Username already exists'}), 409

    user_doc = {
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "phone_number": data["phone_number"],
        "linkedin_url": data["linkedin_url"],
        "email": data["email"],
        "graduated_or_not": data["graduated_or_not"],
        "college": data["college"],
        "degree_name": data["degree_name"],
        "gmail_id": data["gmail_id"],
        "gmail_in_app_password": data["gmail_in_app_password"],
        "gemini_api_key": data["gemini_api_key"],
        "db_url": data["db_url"],
        "roles": data["roles"],
        "username": data["username"],
        "password": generate_password_hash(data["password"]),
        "id": str(uuid.uuid4())
    }
    users_collection.insert_one(user_doc)
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/frontend/meta-data', methods=['GET'])
# @cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def frontend_meta_data():
    print("frontend_meta_data")
    metadata_collection = db['frontend_metadata']
    metadata = metadata_collection.find_one({"entity": "meta_data"})
    if not metadata:
        return jsonify({'error': 'Metadata not found'}), 404
    metadata.pop('_id', None)  # Remove ObjectId if present
    response = jsonify(metadata)
    # response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:5173')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response, 200

@app.route('/meta-data', methods=['GET'])
def get_meta_data():
    meta_data_collection = db['meta_data']
    meta_data_docs = list(meta_data_collection.find())
    for doc in meta_data_docs:
        doc.pop('_id', None)
    return jsonify(meta_data_docs), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    user = users_collection.find_one({'username': username})
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid username or password'}), 401

    # Set session data
    session['username'] = username
    session['user_id'] = str(user.get('id', ''))
    
    # Get user details for session
    details = get_user_details(username)
    session['db_url'] = details.get('db_url', '')

    # Return user info except password
    user_info = {k: v for k, v in user.items() if k != 'password' and k != '_id'}
    
    # Convert roles string to array if it exists
    if 'roles' in user_info and isinstance(user_info['roles'], str):
        user_info['roles'] = [user_info['roles']]
    elif 'roles' not in user_info:
        user_info['roles'] = []
    
    return jsonify({'message': 'Login successful', 'user': user_info}), 200

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logout successful'}), 200

# Suggestions API
@app.route('/suggestions', methods=['GET'])
def suggestions():
    suggestions = [
        {"first_name": "Alice", "last_name": "Johnson", "organization_email_id": "alice.johnson@aws.com", "organization": "Amazon"},
        {"first_name": "Bob", "last_name": "Smith", "organization_email_id": "bob.smith@aws.com", "organization": "Amazon"},
        {"first_name": "Carol", "last_name": "Davis", "organization_email_id": "carol.davis@aws.com", "organization": "Amazon"},
        {"first_name": "David", "last_name": "Wilson", "organization_email_id": "david.wilson@aws.com", "organization": "Amazon"},
        {"first_name": "Eve", "last_name": "Miller", "organization_email_id": "eve.miller@aws.com", "organization": "Amazon"}
    ]
    return jsonify({'suggestions': suggestions}), 200

# Add Employer Details API
@app.route('/employer-details', methods=['GET'])
def add_employer_details():
    resume = request.args.get('resume')
    if not resume:
        return jsonify({'error': 'Missing required query parameter: resume'}), 400
    return jsonify({'resume': resume}), 200

def require_query_param(param_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            value = request.args.get(param_name)
            if not value:
                return jsonify({'error': f'{param_name} is required'}), 400
            # Pass the param value as a keyword argument to the route
            return f(*args, **kwargs, **{param_name: value})
        return decorated_function
    return decorator

@app.route('/view-user-details', methods=['GET'])
def view_user_details():
    # Try to get username from session first, then from query params
    session_username = session.get('username')
    query_username = request.args.get('username')
    username = session_username or query_username
    
    print(f"Session username: {session_username}")
    print(f"Query username: {query_username}")
    print(f"Final username: {username}")
    
    if not username:
        return jsonify({'error': 'User not authenticated'}), 401
    
    user = users_collection.find_one({'username': username})
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.pop('password', None)
    user.pop('_id', None)
    
    # Graduation done conversion
    if user.get('graduated_or_not', '').lower() == 'yes':
        user['graduation_done'] = 'Yes'
    else:
        user['graduation_done'] = 'No'
    
    # Resumes: Use correct path
    resumes_dir = os.path.join(MEDIA_ROOT, username, 'resumes')
    resumes = []
    if os.path.exists(resumes_dir):
        resumes = [f for f in os.listdir(resumes_dir) if f.endswith('.pdf')]
    user['resumes'] = resumes
    
    # Map field names to match frontend expectations
    user['university'] = user.get('college', '')
    user['linkedin_profile'] = user.get('linkedin_url', '')
    
    return jsonify(user), 200

# List Resumes API
@app.route('/resume', methods=['GET'])
@require_query_param('username')
def list_resumes(username):
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    resumes_dir = os.path.join('users', username, 'resumes')
    resumes = []
    if os.path.exists(resumes_dir):
        resumes = [f for f in os.listdir(resumes_dir) if f.endswith('.pdf')]
    return jsonify({'resumes': resumes, 'username': username}), 200

# List Templates API
@app.route('/templates', methods=['GET'])
@require_query_param('username')
def list_templates(username):
    print("list_templates")
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    user = users_collection.find_one({'username': username})
    if not user:
        return jsonify({'error': 'User not found'}), 404
    db_url = user.get('db_url')
    # For now, use main db
    templates = db['email_templates'].find({'username': username})
    _templates = [{'name': t['title'], 'content': t['content']} for t in templates]
    return jsonify({'templates': _templates, 'username': username}), 200

# Companies Datasets API (placeholder, adapt path as needed)
@app.route('/companies-datasets/<username>', methods=['GET'])
def get_companies_datasets(username):
    user_dir = os.path.join('media', username)
    datasets = []
    if os.path.exists(user_dir):
        datasets = [f for f in os.listdir(user_dir) if f.endswith('.json')]
    return jsonify({'datasets': datasets}), 200

# Select Companies API (placeholder, adapt path as needed)
@app.route('/select-companies/<username>', methods=['GET'])
def select_companies(username):
    dataset = request.args.get('dataset')
    if not dataset:
        return jsonify({'error': 'Dataset not selected'}), 400
    user_dir = os.path.join('media', username, dataset)
    if not os.path.exists(user_dir):
        return jsonify({'error': 'Dataset file not found'}), 404
    with open(user_dir, 'r') as f:
        companies = json.load(f)
    return jsonify({'companies': companies}), 200

# Email History API (placeholder, adapt path as needed)
@app.route('/email-history/<username>', methods=['GET'])
def email_history(username):
    user_dir = os.path.join('emailwhiz_api', 'users', username)
    history_file = os.path.join(user_dir, 'history.json')
    resumes_dir = os.path.join(user_dir, 'resumes')
    resumes = []
    if os.path.exists(resumes_dir):
        resumes = [f for f in os.listdir(resumes_dir) if f.endswith('.pdf')]
    if os.path.exists(history_file):
        with open(history_file, 'r') as file:
            history_data = json.load(file)
    else:
        history_data = {"history": []}
    history_by_company = {}
    for entry in history_data["history"]:
        company = entry.get('company')
        if company not in history_by_company:
            history_by_company[company] = []
        history_by_company[company].append(entry)
    return jsonify({'history_by_company': history_by_company, 'resumes': resumes, 'username': username}), 200

# Apollo APIs Curl Update (placeholder, adapt as needed)
@app.route('/apollo-apis/<username>', methods=['GET'])
def update_apollo_apis_(username):
    api_details = db['apollo_apis_curl'].find_one({'username': username})
    if not api_details:
        api_details = {}
        context = {
            'api1_value': api_details.get('api1', {}).get('curl_request', ''),
            'api2_value': api_details.get('api2', {}).get('curl_request', ''),
            'api3_value': api_details.get('api3', {}).get('curl_request', ''),
        }
    else:
        context = {
            'api1_value': api_details["apis"].get('api1', {}).get('curl_request', ''),
            'api2_value': api_details["apis"].get('api2', {}).get('curl_request', ''),
            'api3_value': api_details["apis"].get('api3', {}).get('curl_request', ''),
        }
    return jsonify(context), 200

@app.route('/update-apollo-apis/<api_name>', methods=['GET', 'POST'])
def update_apollo_apis(api_name):
    data = request.get_json() if request.method == 'POST' else {}
    username = data.get('username') or request.args.get('username')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        # Ensure the collection has an entry for this user
        user_entry = apollo_apis_curl_collection.find_one({'username': username})
        if not user_entry:
            apollo_apis_curl_collection.insert_one({'username': username, 'apis': {}})

        if request.method == 'POST':
            curl_request = data.get('curl_request')
            if not curl_request:
                return jsonify({'status': 'error', 'message': 'No curl request provided'}), 400

            # Update the API details for the specific user and API
            apollo_apis_curl_collection.update_one(
                {'username': username},
                {'$set': {f'apis.{api_name}.curl_request': curl_request}}
            )

        # Fetch updated API details
        user_entry = apollo_apis_curl_collection.find_one({'username': username})
        api_details = user_entry.get('apis', {})

        context = {
            'api1_value': api_details.get('api1', {}).get('curl_request', ''),
            'api2_value': api_details.get('api2', {}).get('curl_request', ''),
            'api3_value': api_details.get('api3', {}).get('curl_request', ''),
        }

        return jsonify(context), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/hit-apollo-api/<api_name>', methods=['POST'])
def hit_apollo_api(api_name):
    data = request.get_json()
    username = data.get('username')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        entry = apollo_apis_curl_collection.find_one({'username': username})
        if not entry:
            return jsonify({'error': 'No API configuration found for user'}), 404
        
        api_details = entry.get('apis', {})
        curl_request = api_details.get(api_name, {}).get('curl_request')
        
        if not curl_request:
            return jsonify({'error': f"No CURL request found for {api_name}"}), 404

        # Parse the curl command
        url, headers, data = parse_curl_command(curl_request)
        
        if not url:
            return jsonify({'error': "Invalid CURL request: URL missing"}), 400

        # Perform the HTTP request
        if data:
            response = requests.post(url, headers=headers, data=data)
            if response.status_code == 401: 
                return jsonify({"error": response.content.decode('utf-8')}), 401
        else:
            response = requests.get(url, headers=headers)
        
        if response.status_code == 401:
            return jsonify({"error": response.content.decode('utf-8')}), 401
        
        # Return the response in JSON format
        return jsonify(response.json()), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-companies-id', methods=['POST'])
def get_companies_id():
    data = request.get_json()
    keywords = data.get('keywords', [])
    locations = data.get('locations', [])
    requested_page = data.get('requested_page', 1)
    store_companies = data.get('store_companies', False)
    username = data.get('username')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        details = get_user_details(username)
        user_entry = apollo_apis_curl_collection.find_one({'username': username})
        api_details = user_entry.get('apis', {})

        curl_request = api_details.get('api1', {}).get('curl_request')
        
        if not curl_request:
            return jsonify({'error': f"No CURL request found for Companies API"}), 404

        # Parse the curl command
        url, headers, data = parse_curl_command(curl_request)
        
        data = replace_value_by_key(data, 'organization_locations', locations)
        data = replace_value_by_key(data, 'q_anded_organization_keyword_tags', keywords)
        data = replace_value_by_key(data, 'page', int(requested_page))
        data = replace_value_by_key(data, 'per_page', 25)
        
        if not url:
            return jsonify({'error': "Invalid CURL request: URL missing"}), 400

        # Perform the HTTP request
        all_companies = []
        response = requests.post(url, headers=headers, data=str(data))
        
        if response.status_code == 401: 
            return jsonify({"error": response.content.decode('utf-8')}), 401
        
        response_data = response.json()
        if response.status_code != 200: 
            return jsonify({"error": response_data}), response.status_code
        
        accounts = response_data.get('accounts', [])
        organizations = response_data.get('organizations', [])

        for account in accounts:
            all_companies.append({
                'name': account.get('name'),
                'id': account.get('id'),
                'logo_url': account.get('logo_url'),
                'timestamp': datetime.now(),
                'keywords': keywords,
                'locations': locations
            })

        for organization in organizations:
            all_companies.append({
                'name': organization.get('name'),
                'id': organization.get('id'),
                'logo_url': organization.get('logo_url'),
                'timestamp': datetime.now(),
                'keywords': keywords,
                'locations': locations
            })

        companies_addition_count = 0
        if store_companies:
            if all_companies:
                for company in all_companies:
                    users_db = get_users_db(details['db_url'])
                    companies_collection = users_db['companies']
                    
                    result = companies_collection.update_one(
                        {'id': company['id']},
                        {
                            '$set': {
                                'name': company['name'],
                                'logo_url': company['logo_url'],
                                'timestamp': datetime.now()
                            },
                            '$addToSet': {
                                'keywords': {'$each': keywords},
                                'locations': {'$each': locations}
                            },
                            '$setOnInsert': {
                                'is_processed': False
                            }
                        },
                        upsert=True
                    )
                    if result.modified_count == 0:
                        companies_addition_count += 1

        resp = response.json()
        resp['companies_addition_count'] = companies_addition_count

        return jsonify(resp), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/add-keyword', methods=['POST'])
def add_keyword():
    data = request.get_json()
    new_keyword = data.get('keyword', '').strip()
    username = data.get('username')
    
    if not new_keyword or not username:
        return jsonify({'success': False, 'message': 'Invalid keyword or username'}), 400

    try:
        # Fetch the current keywords from `and_company_keywords`
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        and_collection = users_db['and_company_keywords']
        document = and_collection.find_one({})
        existing_keywords = document.get('keywords', []) if document else []

        # Add the new keyword to the list if it doesn't exist
        if new_keyword in existing_keywords:
            return jsonify({'success': False, 'message': 'Keyword already exists'}), 400

        existing_keywords.append(new_keyword)
        and_collection.update_one({}, {'$set': {'keywords': existing_keywords}}, upsert=True)

        # Generate all combinations of the updated keywords
        all_combinations = []
        for r in range(1, len(existing_keywords) + 1):
            all_combinations.extend(combinations(existing_keywords, r))

        # Update the `combinations_company_keywords` collection
        combination_collection = users_db['combinations_company_keywords']

        combination_collection.delete_many({})  # Clear existing combinations
        new_combinations = [
            {'keywords': list(comb), 'is_processed': False}
            for comb in all_combinations
        ]
        combination_collection.insert_many(new_combinations)

        return jsonify({'success': True, 'message': 'Keyword added and combinations updated'}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500

@app.route('/keyword-counts', methods=['GET'])
def get_keyword_combinations_counts():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        combination_collection = users_db['combinations_company_keywords']
        total_processed = combination_collection.count_documents({'is_processed': True})
        total_unprocessed = combination_collection.count_documents({'is_processed': False})
        return jsonify({
            'processed': total_processed,
            'unprocessed': total_unprocessed
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-companies', methods=['POST'])
def scrape_companies():
    data = request.get_json()
    locations = data.get("locations", [])
    username = data.get('username')
    
    if not locations or not username:
        return jsonify({"error": "Locations and username are required"}), 400
    
    try:
        # Fetch an unprocessed combination
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        combination_collection = users_db['combinations_company_keywords']
        combination = combination_collection.find_one({"is_processed": False})
        
        if not combination:
            return jsonify({"error": "No unprocessed combinations available"}), 404

        keywords = combination.get("keywords", [])
        
        # Create a mock request object for get_companies_id
        class MockRequest:
            def __init__(self, data):
                self._json = data
        
        mock_request = MockRequest({
            'keywords': keywords,
            'locations': locations,
            'requested_page': 1,
            'store_companies': False,
            'username': username
        })
        
        response = get_companies_id()
        
        if "error" in response:
            return jsonify({"error": response}), 400
        
        total_entries = response['pagination']['total_entries']
        if total_entries > 125:
            total_pages = 5
        else:
            total_pages = math.ceil(total_entries/25)
        
        resp = {'companies_addition_count': 0}
        for i in range(1, total_pages+1):
            mock_request._json['requested_page'] = i
            mock_request._json['store_companies'] = True
            response = get_companies_id()
            resp['companies_addition_count'] += response['companies_addition_count']
            time.sleep(60)
        
        # Mark the combination as processed
        combination_collection.update_one(
            {"_id": combination["_id"]},
            {"$set": {"is_processed": True}}
        )

        return jsonify({"success": resp, "keywords": keywords}), 200
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/company-count', methods=['GET'])
def company_count():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        companies_collection = users_db['companies']
        total = companies_collection.count_documents({})
        processed = companies_collection.count_documents({"is_processed": True})
        return jsonify({"total": total, "processed": processed}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/apollo-emails-count', methods=['GET'])
def apollo_emails_count():
    try:
        total = apollo_emails_collection.count_documents({})
        unlocked_emails_count = apollo_emails_collection.count_documents({
            "email": { "$ne": "", "$ne": None }, 
            "email_status": {"$ne": "unavailable"}
        })
        unavailable_emails_count = apollo_emails_collection.count_documents({
            "email": {"$in": [None, ""]}, 
            "email_status": "unavailable"
        })
        return jsonify({
            "total": total, 
            "unlocked_emails_count": unlocked_emails_count, 
            "unavailable_emails_count": unavailable_emails_count
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/emails-sent-count', methods=['GET'])
def emails_sent_count():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        total = apollo_emails_collection.count_documents({})
        
        # Get current system time and convert to UTC
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        apollo_emails_sent_history_collection = users_db['apollo_emails_sent_history']
        today_emails_sent_count = apollo_emails_sent_history_collection.count_documents(
            {"emails.timestamp": {"$gte": today_start, "$lt": today_end}}
        )
        
        unlocked_emails_count = apollo_emails_collection.count_documents({"email": {"$ne": ""}})
        total_sent_emails = apollo_emails_sent_history_collection.count_documents({})
        
        return jsonify({
            "total": total, 
            "unlocked_emails_count": unlocked_emails_count, 
            "total_sent_emails": total_sent_emails, 
            "today_emails_sent_count": today_emails_sent_count
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/employees-count', methods=['GET'])
def employees_count():
    try:
        total = apollo_emails_collection.count_documents({})
        return jsonify({"total": total}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-non-processed-companies', methods=['GET'])
def get_non_processed_companies():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        companies_collection = users_db['companies']
        companies = list(companies_collection.find({"is_processed": False}, {"_id": 0, "logo_url": 0}))
        return jsonify({'companies': companies}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search-companies', methods=['GET'])
def search_companies():
    query = request.args.get("query", "").strip()
    username = request.args.get('username')
    
    if len(query) < 3 or not username:
        return jsonify([]), 200  # Return empty list if query too short or no username

    try:
        # Fetch matching companies
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        companies_collection = users_db['companies']
        matching_companies = companies_collection.find(
            {"name": {"$regex": query, "$options": "i"}},
            {"_id": 0, "id": 1, "name": 1, "logo_url": 1}
        )
        results = []
        apollo_emails_sent_history_collection = users_db['apollo_emails_sent_history']

        for company in matching_companies:
            # Fetch the employee count for the current company
            employee_count = apollo_emails_collection.count_documents({"organization_id": company["id"]})
            emails_unlocked_count = apollo_emails_collection.count_documents({"organization_id": company["id"], "email": {"$ne": ""}})
            verified_emails_count = apollo_emails_sent_history_collection.count_documents({"email_status": "verified"})
            already_emails_sent_count = apollo_emails_sent_history_collection.count_documents({"organization_id": company["id"]})

            company["employees_count"] = employee_count
            company["emails_unlocked_count"] = emails_unlocked_count
            company["verified_emails_count"] = verified_emails_count
            company["already_emails_sent_count"] = already_emails_sent_count

            results.append(company)

        return jsonify(results), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/resume', methods=['POST'])
def save_resume():
    print("save_resume", request.__dict__)
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    file_name = request.form.get('file_name', file.filename)
    username = request.form.get('username')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file:
        upload_dir = os.path.join('users', username, 'resumes')
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, f'{file_name}.pdf')
        file.save(file_path)
        
        return jsonify({'message': 'Resume saved successfully'}), 200
    
    return jsonify({'error': 'Invalid request method'}), 405

@app.route('/email-generator_post', methods=['POST'])
def email_generator_post():
    data = request.get_json()
    username = data.get('username')
    selected_resume = data.get('resume')
    selected_template = data.get('template')
    use_ai = data.get('use_ai', False)
    employers_data = data.get('employers', [])
    
    if not username or not selected_resume or not selected_template:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        details = get_user_details(username)
        gemini_api_key = details['gemini_api_key']
        resume_path = os.path.join(MEDIA_ROOT, username, 'resumes', selected_resume)
        
        users_db = get_users_db(details['db_url'])
        template = users_db['email_templates'].find_one({"title": selected_template, "username": username})
        
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        
        content = template['content']
        generated_emails = []
        
        for employer in employers_data:
            first_name = employer['first_name']
            last_name = employer['last_name']
            recruiter_email = employer['email']
            target_company = employer['company']
            target_role = employer['job_role']
            
            emp_data = {
                'first_name': first_name,
                'last_name': last_name,
                'email': recruiter_email,
                'company': target_company,
                'job_role': target_role,
                'resume_path': resume_path
            }
            
            if use_ai:
                genai.configure(api_key=gemini_api_key)
                generation_config = {
                    "temperature": 1,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                    "response_mime_type": "text/plain",
                }
                
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    generation_config=generation_config,
                )
                
                prompt = f"""
                    I want to send a cold email to recruiter, and I want to use your response directly in the API. I want you to generate an email based on the below template:\n\n 
                    {content}\n\n
                    \n\n Employer details are: \n
                    first_name: {emp_data['first_name']},\n
                    email: {emp_data['email']},\n
                    company: {emp_data['company']},\n
                    job_role: {emp_data['job_role']}\n
                    Few things you need to keep in mind:\n
                    1. I want you to fill up the values in all of the boxes []. Don't miss anyone of them. The response should not contain [....] like thing. If possible search on internet. \n 
                    2. I just want the content of the generated email template in response from your side as I want to use this in an API, so my application is totally dependent on you, so please give me only the content (without subject) in HTML format. \n 
                    3. I want your response as: <html><body>Email Body</body></html> & I want your response in the normal response text block, not in code block so that I can use your response in the API
                """
                
                response = call_gemini_api(prompt, model)
                emp_data['email_content'] = response.text
            else:
                message = content.format(
                    first_name=first_name, 
                    last_name=last_name, 
                    email=recruiter_email, 
                    company_name=target_company, 
                    designation=target_role
                )
                emp_data['email_content'] = message
            
            generated_emails.append(emp_data)
        
        return jsonify({'data': generated_emails}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/send-emails', methods=['POST'])
def send_emails():
    data = request.get_json()
    employers_data = data.get('data', [])
    username = data.get('username')
    
    if not employers_data or not username:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        details = get_user_details(username)
        
        for employer in employers_data:
            name = employer['first_name'] 
            receiver_email = employer['email']
            designation = employer['job_role']
            company_name = employer['company']
            message = employer['email_content']
            resume_path = employer['resume_path']
            subject = f"[{details['first_name']} {details['last_name']}]: Exploring {designation} Roles at {company_name}"
            
            # Import email sender function
            from emailwhiz_api.email_sender import send_email
            send_email(details['gmail_id'], details['gmail_in_app_password'], receiver_email, subject, message, resume_path)
            update_email_history(username, receiver_email, subject, message, company_name, designation)
        
        return jsonify({'message': 'Emails sent successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/templates/create', methods=['POST'])
def create_template_post():
    data = request.get_json()
    template_title = data.get('template_title')
    template_content = data.get('template_content')
    username = data.get('username')
    
    if not template_title or not template_content or not username:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        
        if users_db['email_templates'].find_one({"title": template_title, "username": username}):
            return jsonify({'error': 'Template with this title already exists.'}), 400
        
        users_db['email_templates'].insert_one({
            "title": template_title, 
            "content": template_content, 
            "username": username
        })
        
        return jsonify({'message': 'Template created successfully'}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/templates/list/<username>', methods=['GET'])
def list_templates_(username):
    try:
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        templates = list(users_db['email_templates'].find({"username": username}))
        
        # Remove ObjectId from response
        for template in templates:
            template.pop('_id', None)
        
        return jsonify({'templates': templates}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate_followup', methods=['POST'])
def generate_followup():
    data = request.get_json()
    receiver_email = data.get('receiver_email')
    username = data.get('username')
    
    if not receiver_email or not username:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        details = get_user_details(username)
        user_dir = os.path.join(MEDIA_ROOT, username)
        history_file = os.path.join(user_dir, 'history.json')
        
        if not os.path.exists(history_file):
            return jsonify({'error': 'No email history found'}), 404
        
        with open(history_file, 'r') as file:
            history_data = json.load(file)
        
        recipient_history = next((item for item in history_data["history"] if item["receiver_email"] == receiver_email), None)
        if not recipient_history:
            return jsonify({'error': 'No history found for this recipient.'}), 404
        
        previous_emails = recipient_history["emails"][-2:] if len(recipient_history["emails"]) > 1 else recipient_history["emails"]
        prompt = "\n\n".join([f"Subject: {email['subject']}\nContent: {email['content']}" for email in previous_emails]) + """
        \n\nGenerate a follow-up email based on the above emails in HTML Format. I want to use your response in an API, so give me only the body as your response. \n 
        Give me the response as a json string which I can decode easily in my code for example: {'subject': 'Subject Generated', 'content': '<html><body>Email Body</body></html>'}\n
        I want your response in the normal response text block, not in code block so that I can use your response in the API.\n
        In your response, there should not be any boxes [mention something..]. I don't want to fill the values manuaaly not even date.\n
        Again, give me your response as text block in the format {.....} not in json or code block."""
        
        gemini_api_key = details['gemini_api_key']
        genai.configure(api_key=gemini_api_key)
        
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "text/plain",
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
        )
        
        response = call_gemini_api(prompt, model)
        cleaned_resp = response.text
        
        if cleaned_resp[:7] == '```json':
            cleaned_resp = cleaned_resp[8:-4]
        
        data = json.loads(cleaned_resp)
        return jsonify({"subject": data["subject"], "content": data["content"]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/send_followup', methods=['POST'])
def send_followup():
    data = request.get_json()
    receiver_email = data.get('receiver_email')
    content = data.get('content')
    subject = data.get('subject')
    username = data.get('username')
    
    if not all([receiver_email, content, subject, username]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        details = get_user_details(username)
        
        from emailwhiz_api.email_sender import send_email
        send_email(details['gmail_id'], details['gmail_in_app_password'], receiver_email, subject, content, '')
        
        update_email_history(username, receiver_email, subject, content, '', '')
        return jsonify({'message': 'Follow-up email sent successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/create-subject', methods=['POST'])
def create_subject():
    data = request.get_json()
    username = data.get('username')
    subject_content = data.get("subjectContent")
    subject_title = data.get("subjectTitle")
    
    if not all([username, subject_content, subject_title]):
        return jsonify({"error": "Username, subject content and subject title are required."}), 400

    try:
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        subject_collection = users_db['subjects']
        
        entry = subject_collection.find_one({'subject_title': subject_title})
        if entry:
            return jsonify({"error": "Subject Title Already Exists."}), 400

        # Create and insert the document
        subject_document = {
            "username": username,
            "subject_title": subject_title,
            "subject_content": subject_content,
            "timestamp": datetime.now(),
        }
        
        subject_collection.insert_one(subject_document)
        return jsonify({"message": "Subject saved successfully!"}), 200

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/fetch-subjects', methods=['GET'])
def fetch_subjects():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        subject_collection = users_db['subjects']
        subjects = list(subject_collection.find({"username": username}, {"_id": 0, "subject_title": 1, "subject_content": 1}))
        return jsonify({"success": True, "subjects": subjects}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/get-running-job', methods=['POST'])
def get_running_job():
    data = request.get_json()
    username = data.get('username')
    admin_view = data.get('admin_view', False)
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        jobs = db['jobs']
        
        # Find the running job for the user
        if admin_view:
            running_jobs = list(jobs.find({"status": "running"}, {"_id": 0}))
        else:
            running_jobs = list(jobs.find({"username": username, "status": "running"}, {"_id": 0}))
        
        if running_jobs:
            return jsonify({"jobs": running_jobs}), 200
        else:
            return jsonify({"error": "No running job found for the user."}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-job-history', methods=['POST'])
def get_job_history():
    data = request.get_json()
    username = data.get('username')
    admin_view = data.get('admin_view', False)
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        jobs = db['jobs']
        
        if admin_view:
            job_history = list(jobs.find({}, {"_id": 0}).sort("created_at", -1))
        else:
            job_history = list(jobs.find({"username": username}, {"_id": 0}).sort("created_at", -1))

        if job_history:
            return jsonify({"jobs": job_history}), 200
        else:
            return jsonify({"error": "No job history found for the user."}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/scheduler/<action>', methods=['GET', 'POST'])
def scheduler_control(action):
    data = request.get_json() if request.method == 'POST' else {}
    username = data.get('username') or request.args.get('username')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        details = get_user_details(username)
        roles = details.get('roles', [])
        
        if 'admin' not in roles:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        # Get environment parameter
        env = None
        if action == 'status':
            env = request.args.get('env')
        else:
            env = data.get('env')
        
        if not env:
            return jsonify({'success': False, 'error': 'Missing environment parameter'}), 400

        valid_actions = ['running', 'stopped', 'status']
        if action not in valid_actions:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400

        scheduler_meta_collection = db["job_scheduler_meta"]
        
        if action in ['running', 'stopped']:
            new_status = 'running' if action == 'running' else 'stopped'
            
            result = scheduler_meta_collection.update_one(
                {"identifier": "running_state", "env": env},
                {"$set": {"status": new_status}},
                upsert=True
            )
            
            # Note: You'll need to implement the cron_job_scheduler functionality
            # if new_status == 'running':
            #     cron_job_scheduler.start_scheduler(env)
            # else:
            #     cron_job_scheduler.stop_scheduler(env)
            
            if result.modified_count > 0 or result.upserted_id:
                return jsonify({'success': True}), 200
            return jsonify({'success': False, 'error': 'Update failed'}), 500
        
        elif action == 'status':
            status_doc = scheduler_meta_collection.find_one({"identifier": "running_state", "env": env})
            status = status_doc.get('status', 'stopped') if status_doc else 'stopped'
            return jsonify({'success': True, 'status': status}), 200
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/scheduler/status', methods=['GET'])
def scheduler_status():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    try:
        details = get_user_details(username)
        roles = details.get('roles', [])
        
        if 'admin' not in roles:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        env = request.args.get('env')
        if not env:
            return jsonify({'success': False, 'error': 'Missing environment parameter'}), 400

        scheduler_meta_collection = db["job_scheduler_meta"]
        
        status_doc = scheduler_meta_collection.find_one({"identifier": "running_state", "env": env})
        
        status = status_doc.get('status', 'stopped') if status_doc else 'stopped'
        return jsonify({
            'success': True,
            'status': status,
            'environment': env,
            'last_updated': status_doc.get('updated_at') if status_doc else None
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500

@app.route('/apollo/send-cold-emails-by-automation', methods=['POST'])
def send_cold_emails_by_automation_through_apollo_emails():
    try:
        # Import the automation module
        from apollo.cold_emails.automation import send_cold_emails_by_automation_through_apollo_emails as automation_function
        return automation_function(request)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/apollo/send-cold-emails-by-company', methods=['POST'])
def send_cold_emails_by_company_through_apollo_emails():
    try:
        # Import the by_company module
        from apollo.cold_emails.by_company import send_cold_emails_by_company_through_apollo_emails as company_function
        return company_function(request)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fetch-employees', methods=['POST'])
def fetch_employees():
    data = request.get_json()
    company_info = data.get("company_id", None)
    locations = data.get('locations', None)
    auto = data.get("auto", False)
    titles = data.get("job_titles", None)
    number_of_companies = data.get("number_of_companies", 1)
    username = data.get('username')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    if titles is None or locations is None:
        return jsonify({"error": 'Job Titles or Locations are Missing'}), 400
    
    try:
        details = get_user_details(username)
        entry = apollo_apis_curl_collection.find_one({'username': username})
        api_details = entry.get('apis', {})
        curl_request = api_details.get('api2', {}).get('curl_request')
        users_db = get_users_db(details['db_url'])
        jobs = db['jobs']
        
        existing_job = jobs.find_one({"username": username, "status": "running"})
        if existing_job:
            return jsonify({
                "error": f"A job of type '{existing_job['id']}' is already running for this user. Please wait for it to complete."
            }), 400
        
        executor = ThreadPoolExecutor(max_workers=5)
        if auto == False:
            number_of_companies = 1
        
        temp_data = {
            'username': username, 
            'company_info': company_info,
            'locations': locations, 
            'auto': auto,
            'job_titles': titles,
            'number_of_companies': number_of_companies,
            'curl_request': curl_request
        }
        
        # Note: You'll need to implement the fetch_employees_job function
        # executor.submit(fetch_employees_job, request, temp_data)

        return jsonify({"success": True, "message": "Job has started"}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fetch-employees-emails', methods=['POST'])
def fetch_employees_emails():
    data = request.get_json()
    username = data.get('username')
    company_info = data.get("company_id", None)
    locations = data.get('locations', None)
    auto = data.get("auto", False)
    titles = data.get("job_titles", None)
    search_filters = data.get("search_filters", [])
    number_of_companies = data.get("number_of_companies", 1)
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    if titles is None or locations is None:
        return jsonify({"error": 'Job Titles or Locations are Missing'}), 400
    
    try:
        entry = apollo_apis_curl_collection.find_one({'username': username})
        api_details = entry.get('apis', {})
        curl_request = api_details.get('api3', {}).get('curl_request')
        
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        jobs = db['jobs']
        
        existing_job = jobs.find_one({"username": username, "status": "running"})
        if existing_job:
            return jsonify({
                "error": f"A job of type '{existing_job['id']}' is already running for this user. Please wait for it to complete."
            }), 400
        
        executor = ThreadPoolExecutor(max_workers=5)
        temp_data = {
            'username': username, 
            'company_info': company_info,
            'locations': locations, 
            'auto': auto,
            'job_titles': titles,
            'number_of_companies': number_of_companies,
            'curl_request': curl_request,
            'search_filters': search_filters
        }
        
        # Note: You'll need to implement the unlock_emails_job function
        # executor.submit(unlock_emails_job, request, temp_data)

        return jsonify({"success": True, "message": "Job has started"}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)