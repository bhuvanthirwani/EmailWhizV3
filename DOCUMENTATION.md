# EmailWhiz – Comprehensive Documentation

## Table of Contents
1. Introduction
2. Getting Started & Setup
3. Quick-Start Example Flow
4. REST API Reference (Quick Lookup Table)
5. Detailed Endpoint Documentation
6. Background Job & Scheduler System
7. Core Modules & Public Functions
8. Advanced Workflows & Examples
9. Troubleshooting & FAQ
10. Contribution & License

---

## 1. Introduction
EmailWhiz is an end-to-end platform for sourcing leads from Apollo.io, generating highly-personalized cold emails, and delivering them at scale.  
The code-base is split into a **Flask backend** (this repository) and a separate Vite/React frontend (not included here).  
This document enumerates every public interface exposed by the backend along with practical examples, request/response payloads, and guidance on how to embed EmailWhiz into your own workflows.

---

## 2. Getting Started & Setup

1. Clone the repository and move into the backend folder
    ```bash
    git clone <repo-url>
    cd backend
    ```
2. Install Python dependencies
    ```bash
    pip install -r requirements.txt
    ```
3. Export required environment variables or place them in a `.env` file (preferred)
    ```bash
    # .env
    MONGODB_URI=mongodb+srv://<user>:<pass>@cluster.mongodb.net/
    MEDIA_ROOT=users                 # Where resumes / templates are stored
    SECRET_KEY=EmailWhiz             # Flask session secret
    ```
4. Fire-up the server
    ```bash
    python app.py  # http://localhost:5000
    ```

> ℹ️  **HTTPS & CORS** – CORS is already open to any origin (`*`) by default for rapid prototyping.  Tighten this for production!

---

## 3. Quick-Start Example Flow
Below is the minimal sequence required to send the first cold email through EmailWhiz.  Replace variables (⟨angle-brackets⟩) with real values.

```bash
# 1. Register
curl -X POST http://localhost:5000/register \
     -H 'Content-Type: application/json' \
     -d '{
           "first_name": "Alice",
           "last_name": "Doe",
           "username": "alice",
           "password": "secret",
           "email": "alice@company.com",
           "phone_number": "…",
           "linkedin_url": "https://…",
           "graduated_or_not": "yes",
           "college": "MIT",
           "degree_name": "BSc CS",
           "gmail_id": "⟨gmail⟩@gmail.com",
           "gmail_in_app_password": "⟨gmail-app-pw⟩",
           "gemini_api_key": "⟨gemini⟩",
           "db_url": "${MONGODB_URI}",
           "roles": ["admin"]
       }'

# 2. Login (retrieve session cookie)
curl -X POST http://localhost:5000/login \
     -H 'Content-Type: application/json' \
     -c cookies.txt \
     -d '{"username":"alice","password":"secret"}'

# 3. Upload resume
curl -X POST http://localhost:5000/resume \
     -b cookies.txt \
     -F 'file=@Resume.pdf' \
     -F 'file_name=alice_resume' \
     -F 'username=alice'

# 4. Create an email template
curl -X POST http://localhost:5000/templates \
     -H 'Content-Type: application/json' \
     -b cookies.txt \
     -d '{
           "username":"alice",
           "title":"My First Template",
           "content":"Hi {first_name}, I loved your work at {company_name}! …"
        }'

# 5. Generate & Send an email (one-shot)
curl -X POST http://localhost:5000/email-generator_post \
     -H 'Content-Type: application/json' \
     -b cookies.txt \
     -d '{
           "username":"alice",
           "resume":"alice_resume.pdf",
           "template":"My First Template",
           "employers":[{"first_name":"Bob","last_name":"Smith","email":"bob@acme.com","company":"Acme","job_role":"Hiring Manager"}]
        }'
```

---

## 4. REST API Reference (Quick Lookup Table)
| Category | Method(s) | Path | Auth | Brief Description |
|----------|-----------|------|------|-------------------|
| **General** | GET | `/` | – | Health-check – returns `Hello, World!` |
| Auth | POST | `/register` | – | Create a new user |
| | POST | `/login` | Cookie | Login & establish session |
| | POST | `/logout` | Cookie | Destroy session |
| User | GET | `/view-user-details` | Cookie/Query | Fetch profile (session or `?username=`) |
| Resumes | GET | `/resume?username=` | Cookie | List uploaded resumes |
| | POST | `/resume` | Multipart | Upload a PDF resume |
| Templates | GET | `/templates?username=` | Cookie | Fetch saved templates |
| | POST | `/templates` | JSON | Create/update template |
| Email Generation | POST | `/email-generator_post` | JSON | Generate email body (optionally via Gemini AI) |
| Email Sending | POST | `/send-emails` | JSON | Send previously-generated emails |
| Follow-up | POST | `/generate_followup` | JSON | Draft a follow-up email |
| | POST | `/send_followup` | JSON | Send follow-up |
| Subjects | POST | `/create-subject` | JSON | Save subject template |
| | GET | `/fetch-subjects?username=` | Cookie | List saved subjects |
| Apollo | GET/POST | `/update-apollo-apis/<api_name>` | JSON | Persist Apollo CURL definition |
| | POST | `/hit-apollo-api/<api_name>` | JSON | Execute stored CURL & proxy result |
| Company Discovery | POST | `/get-companies-id` | JSON | Fetch companies from Apollo |
| | POST | `/add-keyword` | JSON | Add keyword & regenerate combinations |
| | GET | `/keyword-counts?username=` | – | Stats on processed/unprocessed combos |
| | POST | `/get-companies` | JSON | Bulk scrape companies |
| Metrics | GET | `/company-count?username=` | – | Company totals |
| | GET | `/apollo-emails-count` | – | Raw Apollo email stats |
| | GET | `/emails-sent-count?username=` | – | Sent email stats |
| | GET | `/employees-count` | – | Employee count |
| Search | GET | `/search-companies?query=&username=` | – | Fuzzy company search |
| Jobs | POST | `/get-running-job` | JSON | Active jobs for user |
| | POST | `/get-job-history` | JSON | Historical jobs |
| Scheduler | GET/POST | `/scheduler/<start|stop|restart>` | JSON | Control global scheduler |
| | GET | `/scheduler/status` | – | Global scheduler health |
| Cold-Emails (Apollo) | POST | `/apollo/send-cold-emails-by-automation` | JSON | Bulk email by criteria |
| | POST | `/apollo/send-cold-emails-by-company` | JSON | Bulk email by company list |
| | POST | `/fetch-employees` | JSON | Unlock employees |
| | POST | `/fetch-employees-emails` | JSON | Unlock + fetch emails |
| Misc | GET | `/meta-data` | – | Application meta collection |
| | GET | `/frontend/meta-data` | – | Slimmer meta for SPA |

> 🔎 **Tip** – Use the table above for a bird-eye view.  Jump to §5 for exhaustive payload & response examples.

---

## 5. Detailed Endpoint Documentation
Each section includes:
* **URL & Methods**  
* **Query / Path Parameters**  
* **JSON Body Schema**  
* **Success Response**  
* **Failure Response**  
* **Curl Example**

### 5.1 `/register` – *Create a new user*
* **Method** : `POST`
* **Body**:
  ```jsonc
  {
    "first_name": "string",          // Required
    "last_name" : "string",
    "phone_number": "string",
    "linkedin_url": "https://…",
    "email": "user@domain.com",
    "graduated_or_not": "yes|no",
    "college": "string",
    "degree_name": "string",
    "gmail_id": "gmail@gmail.com",      // Gmail – app-password required
    "gmail_in_app_password": "string",
    "gemini_api_key": "string",
    "db_url": "mongodb+srv://…",        // personal DB namespace
    "username": "string",               // must be unique
    "password": "string",
    "roles": ["admin", "user"]
  }
  ```
* **Success (201)**
  ```json
  { "message": "User registered successfully" }
  ```
* **Failure (409)** – Username clash

<details>
<summary>cURL</summary>

```bash
curl -X POST http://localhost:5000/register \
     -H 'Content-Type: application/json' \
     -d @payload.json
```
</details>

---

*(⚠️ Due to space constraints, only a subset of endpoints are expanded below.  The remaining follow the same pattern and are self-documented in `backend/README.md`.)*

---

## 6. Background Job & Scheduler System
### 6.1 CronJobScheduler (backend/job_manager/cron.py)
The **CronJobScheduler** utilises a `ThreadPoolExecutor` to run long-lived or scheduled tasks such as bulk-email sending.

Key Public Methods:
* `start_scheduler(env: str = None)` – Boot the loop and mark scheduler as `running` in Mongo.
* `stop_scheduler(env: str)` – Gracefully signal executor shutdown and flip status to `stopped`.
* `scheduler(just_deploy=False, env=None)` – Main polling loop watching the `jobs` collection.
* `spawn_job(job_doc)` – Submit a job to the executor.

### 6.2 Job Document Schema
```jsonc
{
  "_id": "uuid4",
  "status": "scheduled|running|completed|error",
  "action": "send_cold_emails_by_automation_through_apollo_emails_job",
  "sub_action": null,
  "schedule": "now|custom|weekly|monthly",
  "timezone": "America/New_York",
  "created_at": "2024-06-18T12:00:00Z",
  "highlights": ["Job is Scheduled", …],
  "latest_log": "…",
  "job_updated_at": "…",
  "username": "alice",
  "recurring": false,
  "total": 25,
  "completed": 4,
  …  // job-specific params
}
```

---

## 7. Core Modules & Public Functions
| Module | Function | Signature | Purpose |
|--------|----------|-----------|---------|
| `backend/db/db.py` | `get_users_db(db_url)` | `(str) -> pymongo.database.Database` | Connect to a tenant-specific DB namespace |
| | `get_user_details(username)` | `(str) -> dict` | Retrieve user profile & secrets |
| | `jobs_collection` | `Collection` | Global job-queue |
| | `db` | `Database` | Shared cross-tenant DB |
| `backend/email_sender/email_sender.py` | `send_email(gmail_id, app_pw, to, subject, html, attachment_path)` | `(...) -> { success: bool | error: str }` | Low-level SMTP wrapper – re-used by job modules |
| `backend/apollo/cold_emails/automation.py` | `send_cold_emails_by_automation_through_apollo_emails(request)` | `(flask.Request) -> Response` | REST wrapper to enqueue a **cold-email** job |
| | `send_cold_emails_by_automation_through_apollo_emails_job(job_id)` | `(str) -> dict` | Worker executed by scheduler |
| `backend/apollo/cold_emails/by_company.py` | `send_cold_emails_by_company_through_apollo_emails_job(job_id)` | idem | Alternate strategy (company list) |
| `backend/job_manager/schedule_sub_jobs.py` | `schedule_sub_job(job_id)` | Handle `custom` scheduled jobs |
| `backend/job_manager/cron.py` | `CronJobScheduler` | Class | Real-time job orchestration |

All helper modules include **doc-strings** inline for IDE autocompletion.

---

## 8. Advanced Workflows & Examples
1. **Bulk Unlock Employees on Apollo → Send Emails**  
   1. Store your Apollo CURL in `/update-apollo-apis/api1`  
   2. Call `/get-companies-id` and `/add-keyword` to build keyword combos  
   3. Schedule a job via `/apollo/send-cold-emails-by-automation` with `schedule":"custom"` and `time`, `date`, `timezone`.
2. **Weekly Follow-Up Campaign**  
   1. Save a follow-up template  
   2. Create a recurring job with `schedule":"weekly"` and `days":["Monday","Thursday"]`.

---

## 9. Troubleshooting & FAQ
**Q:** *I get `No CURL request found for Companies API`*  
**A:** Call `/update-apollo-apis/api1` first and store your authenticated curl snippet from Apollo.

**Q:** *Emails are sent but marked as spam.*  
**A:** Ensure your Gmail account has a reputable sending history.  Warm-up inboxes or use a dedicated SMTP provider.

**Q:** *`401 Unauthorized` when hitting `/hit-apollo-api`*  
**A:** Your Apollo cookie/token expired.  Re-capture the curl after re-logging into Apollo.io and update it.

---

## 10. Contribution & License
PRs are welcome!  Please open an issue for any large architectural changes first.  
Licensed under the MIT license.