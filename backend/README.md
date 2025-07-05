# EmailWhiz Backend - Flask Version

This is a Flask-based backend application converted from Django. It provides APIs for email automation, Apollo integration, and job scheduling.

## Features

- User authentication and management
- Email template management
- Resume upload and management
- Apollo API integration for lead generation
- Cold email automation
- Job scheduling and management
- Email history tracking

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables (create a `.env` file):
```
MONGODB_URI=mongodb+srv://your_username:your_password@your_cluster.mongodb.net/
MEDIA_ROOT=media
```

3. Create necessary directories:
```bash
mkdir -p media
```

## Running the Application

```bash
python app.py
```

The application will run on `http://localhost:5000` by default.

## API Endpoints

### Authentication
- `POST /register` - User registration
- `POST /login` - User login
- `POST /logout` - User logout

### Resume Management
- `POST /save_resume` - Upload resume
- `GET /resumes/<username>` - List user resumes

### Email Templates
- `POST /templates/create` - Create email template
- `GET /templates/list/<username>` - List user templates

### Email Generation
- `POST /email-generator_post` - Generate personalized emails
- `POST /send-emails` - Send generated emails
- `POST /generate_followup` - Generate follow-up emails
- `POST /send_followup` - Send follow-up emails

### Apollo Integration
- `GET/POST /update-apollo-apis/<api_name>` - Update Apollo API configurations
- `POST /hit-apollo-api/<api_name>` - Execute Apollo API calls
- `POST /get-companies-id` - Fetch companies from Apollo
- `POST /add-keyword` - Add keywords for company search
- `GET /keyword-counts` - Get keyword combination counts
- `POST /get-companies` - Scrape companies
- `GET /company-count` - Get company statistics
- `GET /apollo-emails-count` - Get Apollo email statistics
- `GET /emails-sent-count` - Get sent email statistics
- `GET /employees-count` - Get employee statistics
- `GET /get-non-processed-companies` - Get unprocessed companies
- `GET /search-companies` - Search companies

### Subject Management
- `POST /create-subject` - Create email subject
- `GET /fetch-subjects` - Get user subjects

### Job Management
- `POST /get-running-job` - Get currently running jobs
- `POST /get-job-history` - Get job history

### Scheduler Control
- `GET/POST /scheduler/<action>` - Control job scheduler
- `GET /scheduler/status` - Get scheduler status

### Apollo Cold Emails
- `POST /apollo/send-cold-emails-by-automation` - Send automated cold emails
- `POST /apollo/send-cold-emails-by-company` - Send company-specific cold emails
- `POST /fetch-employees` - Fetch employees from Apollo
- `POST /fetch-employees-emails` - Fetch employee emails from Apollo

### Metadata
- `GET /meta-data` - Get metadata collection
- `GET /frontend/meta-data` - Get frontend metadata

## Directory Structure

```
EmailWhiz-Backend/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── media/                # File storage directory
├── apollo/               # Apollo integration modules
│   └── cold_emails/
│       ├── automation.py
│       └── by_company.py
├── job_manager/          # Job scheduling modules
│   ├── cron.py
│   └── schedule_sub_jobs.py
└── venv/                 # Virtual environment (if used)
```

## Notes

- The application uses MongoDB for data storage
- File uploads are stored in the `media/` directory
- The job scheduler runs in the background using ThreadPoolExecutor
- Apollo API integration requires proper API keys and configurations
- Email sending requires Gmail app passwords

## Conversion Notes

This application was converted from Django to Flask. Key changes include:

- Replaced Django views with Flask routes
- Updated request handling from Django's `request.body` to Flask's `request.get_json()`
- Replaced Django's `JsonResponse` with Flask's `jsonify`
- Updated database connections to use direct PyMongo instead of Django ORM
- Removed Django-specific imports and dependencies
- Updated file path handling to use relative paths instead of Django settings 