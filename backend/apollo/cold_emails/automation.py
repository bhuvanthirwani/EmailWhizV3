from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
import time
import uuid
import traceback
from email_sender.email_sender import send_email
from flask import jsonify, request, session

from db.db import get_users_db, get_user_details, jobs_collection

# Media root for file storage
MEDIA_ROOT = 'users'

def send_cold_emails_by_automation_through_apollo_emails_job(job_id):
    try:
        sub_job_id = str(uuid.uuid4())
        
        job_details = jobs_collection.find_one({"_id": job_id})
        username = job_details['username']
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        number_of_emails = job_details.get("number_of_emails", 1)
        # sub_job_document = {
        #     "total": number_of_emails,
        #     "completed": 0,
        #     "latest_log": "Started",
        #     "status": "running",
        #     "id": sub_job_id,
        #     "highlights": [],
        #     "created_at": datetime.utcnow()
        # }
        # jobs_collection.update_one({"_id": job_id}, {"$push": {"sub_jobs": sub_job_document}})
        
        subject_collection = users_db['subjects']
        apollo_emails_sent_history_collection = users_db['apollo_emails_sent_history']
        companies_collection = users_db['companies']
        selected_subject = job_details.get("selected_subject", None)
        locations = job_details.get("locations", None)
        job_titles = job_details.get("job_titles", None)
        target_role = job_details.get("target_role", None)
        selected_template = job_details.get("selected_template", None)
        resume_name = job_details.get("resume_name", None)
        completed = job_details.get("completed", 0)
        start_time = datetime.now()
        

        if selected_subject:
            
            temp_subject = subject_collection.find_one({"username": username}, {"_id": 0, "subject_title": 1, "subject_content": 1})
            print("subject: ", temp_subject)
        print("locations: ", locations)
        apollo_emails_collection = users_db['apollo_emails']
        employees = list(apollo_emails_collection.find({
            # "titles": {"$in": job_titles},
            "country": {"$in": locations},
            "$and": [
    { "email": { "$exists": True } },
    { "email": { "$ne": None } },
    { "email": { "$ne": "" } }
  ],
            "email_status": "verified"
            }))
        print("len(employees): ", len(employees), (datetime.now() - start_time).total_seconds())
        print("Number of Emails to be sent: ", number_of_emails-completed)
        
        for i in range(completed, number_of_emails):
            _job = jobs_collection.find_one({"_id": job_id})
            if _job["status"] != "running":
                log_message = f"Job state got changed to {_job['status']} while sending emails."
                jobs_collection.update_one(
                    {"_id": job_id}, 
                    {
                        "$set": {"status": "error", "latest_log": log_message, "job_updated_at": datetime.utcnow()},
                        "$push": {"highlights": log_message}
                    }
                )
                return {"error": f"Job state got changed to {_job['status']} while sending emails."}
            
            # Filter employees whose entries are not in apollo_emails_sent_history for the target_role
            employee_details = None
            employee_ids = [employee["id"] for employee in employees]

            # Query the sent history collection for existing records matching person_id and target_role
            
            existing_sent_records = list(apollo_emails_sent_history_collection.find({
                "person_id": {"$in": employee_ids},
                "emails.target_role": target_role,
                "username": username
            }, {"person_id": 1}))

            # Extract IDs of employees who already have emails sent for the target role
            already_sent_ids = {record["person_id"] for record in existing_sent_records}
            print("already_sent_ids", len(already_sent_ids))
            # Find the first employee who hasn't been sent an email for the target role
            employee_details = next((employee for employee in employees if employee["id"] not in already_sent_ids), None)

            if not employee_details:
                log_message = "Unable to send Emails as None Emails are Filtered according to your input or All the Emails for your input have been already sent OR There are No Emails which are Unlocked."
                jobs_collection.update_one(
                    {"_id": job_id}, 
                    {
                        "$set": {
                            "status": "error", 
                            "latest_log": log_message,
                            "job_updated_at": datetime.utcnow()
                        },
                        "$push": {
                            "highlights": log_message
                        }
                    }
                )
                return {"error": f"Unable to send Emails as None Emails are Filtered according to your input or All the Emails for your input have been already sent OR There are No Emails which are Unlocked.", "count": 0}
            
            print(employee_details, len(employee_details), (datetime.now() - start_time).total_seconds())
            # print(employee_details, len(employee_details), (datetime.now() - start_time).total_seconds())
            receiver_first_name = employee_details["first_name"]
            receiver_last_name = employee_details["last_name"]
            employee_email = employee_details["email"]
            organization_id = employee_details["organization_id"]
            company_details = companies_collection.find_one({"id": organization_id})
            print("organization_id: ", organization_id, employee_details, (datetime.now() - start_time).total_seconds())
            company_name = company_details["name"]
            
            existing_email_history = apollo_emails_sent_history_collection.find_one(
                {
                    "person_id": employee_details["id"],
                    "organization_id": organization_id,
                    "emails.target_role": target_role,
                    "username": username
                }
            )
            print("heroic3: ", (datetime.now() - start_time).total_seconds(), employee_email)
            if existing_email_history:
                log_message = f"Email already sent to the {employee_email} for the target role: {target_role}"
                jobs_collection.update_one(
                    {"_id": job_id}, 
                    {
                        "$set": {
                            "status": "error", 
                            "latest_log": log_message,
                            "job_updated_at": datetime.utcnow()
                        },
                        "$push": {
                            "highlights": log_message
                        }
                    }
                )

                return {"error": f"Email already sent to the {employee_email} for the target role: {target_role}"}
            
            subject_details = {
                'first_name': details['first_name'], 
                'last_name': details['last_name'],
                'target_role': target_role, 
                'company_name': company_name
            }
            print("Subect Details: ", subject_details)

            subject = temp_subject["subject_content"]
            for variable in ['first_name', 'last_name', 'target_role', 'company_name']:
                if variable in subject and variable in subject_details:
                    # print("subject_details[variable]: ", subject_details[variable])
                    subject = subject.replace("{" + variable + "}", subject_details[variable])
                    # print("S: ", subject)

            print("subject2: ", subject, (datetime.now() - start_time).total_seconds())
            # subject = f"[{details['first_name']} {details['last_name']}]: Exploring {target_role} Roles at {company_name}"
            print(MEDIA_ROOT, username, 'templates', selected_template,'resumes', resume_name)
            # template_path = os.path.join(settings.MEDIA_ROOT, username, 'templates', selected_template)
            # with open(template_path, 'r') as f:
            #     content = f.read()
            users_db = get_users_db(details['db_url'])
            template = users_db['email_templates'].find_one({"title": selected_template, "username": details['username']})
            content = template['content']
            resume_path = os.path.join(MEDIA_ROOT, username, 'resumes', resume_name)
            print("resume_path: ", resume_path)
            
            personalized_message = content.format(first_name=receiver_first_name, last_name=receiver_last_name, email=employee_email, company_name=company_name, designation=target_role)
            # employee_email="shoaibthakur.23@gmail.com"
            log_message = f"Trying to send Email to {employee_email} | {employee_details['id']} for the target role: {target_role}"
            jobs_collection.update_one(
                    {"_id": job_id}, 
                    {
                        "$set": {
                            "latest_log": log_message,
                            "job_updated_at": datetime.utcnow()
                        },
                        "$push": {
                            "highlights": log_message
                        }
                    }
                )
            response = send_email(details['gmail_id'], details['gmail_in_app_password'], employee_email, subject, personalized_message, resume_path)
            if response.get("error", None):
                log_message = f"Error: {response['error']}"
                jobs_collection.update_one(
                    {"_id": job_id}, 
                    {
                        "$set": {"status": "error", "latest_log": log_message, "job_updated_at": datetime.utcnow()},
                        "$push": {"highlights": log_message}
                    }
                )
                return {"error": f"Error: {response['error']}"}
            
            time.sleep(0.25)
            existing_entry = apollo_emails_sent_history_collection.find_one(
                {"person_id": employee_details["id"], "organization_id": organization_id, "username": username}
            )
            new_email_entry = {
                "subject": subject,
                "content": personalized_message,
                "target_role": target_role,
                "timestamp": datetime.now(),
            }

            if existing_entry:
                # Append the new email entry to the existing emails array
                apollo_emails_sent_history_collection.update_one(
                    {"_id": existing_entry["_id"], "username": username},
                    {"$push": {"emails": new_email_entry}}
                )
                print("Entry Exist, We have started pushing.....")
            else:
                print("Entry Not Exist, We have started pushing.....")
                # Create a new document if no history exists
                email_history_entry = {
                    "person_id": employee_details["id"],
                    "receiver_email": employee_email,
                    "company": company_name,
                    "organization_id": organization_id,
                    "emails": [new_email_entry],
                    "sender_email": details['gmail_id'],
                    "username": username
                }
                apollo_emails_sent_history_collection.insert_one(email_history_entry)
            log_message = f"Email Sent to the {employee_email} for the target role: {target_role}"
            jobs_collection.update_one(
                {"_id": job_id}, 
                {
                    "$set": {
                        "completed": i+1, 
                        "latest_log": log_message,
                        "job_updated_at": datetime.utcnow()
                    },
                    "$push": {
                        "highlights": log_message
                    }
                }
            )
        log_message = f"Sent Successfully to {number_of_emails} Emails"
        jobs_collection.update_one(
            {"_id": job_id}, 
            {
                "$set": {
                    "status": "completed", 
                    "latest_log": log_message,
                    "job_updated_at": datetime.utcnow()
                },
                "$push": {
                    "highlights": log_message
                }
            }
        )
        return {"success": f"All the Emails are Sent Successfully"}
    except Exception as exc:
        traceback.print_exc()
        log_message = f"Error: {exc}"
        jobs_collection.update_one(
            {"_id": job_id}, 
            {
                "$set": {
                    "status": "error", 
                    "latest_log": log_message
                },
                "$push": {
                    "highlights": log_message
                }
            }
        )
        return {"error": f"{exc}"}

def send_cold_emails_by_automation_through_apollo_emails(request):

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    username = data.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400
    details = get_user_details(username)
    users_db = get_users_db(details['db_url'])
    # print("company_id: ", company_info)
    locations = data.get('locations', None)
    cron_job_description = data.get("cron_job_description", None)
    cron_job_name = data.get("cron_job_name", None)
    _time = data.get("time", None)
    date = data.get("date", None)
    timezone = data.get("timezone", None)
    recurring = data.get("recurring", False)
    days = data.get("days", None)
    schedule = data.get("schedule", None)
    number_of_emails = data.get("number_of_emails", 1)
    job_titles = data.get("job_titles", None)
    target_role = data.get("target_role", None)
    selected_template = data.get("selected_template", None)
    selected_subject = data.get("selected_subject", None)
    resume_name = data.get("selected_resume", None)
    number_of_jobs = data.get("number_of_jobs")
    print("loctions, job_titles, target_role, selected_template, resume_name, selected_subject", locations, job_titles, target_role, selected_template, resume_name, selected_subject)
    details = get_user_details(username)
    
    users_db = get_users_db(details['db_url'])
    jobs = jobs_collection
    existing_job = jobs.find_one({"username": username, "status": "running", "action": "send_cold_emails_by_automation_through_apollo_emails_job"})
    if existing_job:
        return jsonify({
            "error": f"A job of type '{existing_job['id']}' is already running for this user. Please wait for it to complete."
        }), 400
    if schedule == 'now':
        job_document = {
            '_id': str(uuid.uuid4()),
            'status': 'scheduled',
            'action': 'send_cold_emails_by_automation_through_apollo_emails_job',
            'sub_action': None,
            'created_at': datetime.utcnow(),
            'latest_log': "Job is Scheduled",
            'highlights': [],
            'job_name': 'Send Cold Emails by Automation',
            'job_updated_at': datetime.utcnow(),
            'schedule': schedule,
            'username': username,
            'locations': locations, 
            'job_titles': job_titles,
            'number_of_emails': number_of_emails,
            'target_role': target_role,
            'selected_template': selected_template,
            'selected_subject': selected_subject,
            'resume_name': resume_name,
            'recurring': recurring,
            'completed': 0,
            'total': number_of_emails
        }
    elif schedule == 'custom':
        job_document = {
            '_id': str(uuid.uuid4()),
            'status': 'scheduled',
            'action': 'schedule_sub_job',
            'sub_action': 'send_cold_emails_by_automation_through_apollo_emails_job',
            'created_at': datetime.utcnow(),
            'latest_log': "Job is Scheduled",
            'highlights': [],
            'job_updated_at': datetime.utcnow(),
            'schedule': 'now',
            'username': username, 
            'locations': locations, 
            'job_titles': job_titles,
            'cron_job_description': cron_job_description,
            'cron_job_name': cron_job_name,
            'job_name': cron_job_name,
            'sub_job_name': 'Send Cold Emails by Automation',
            'number_of_emails': number_of_emails,
            'time': _time,
            'date': date,
            'timezone': timezone,
            'recurring': recurring,
            'target_role': target_role,
            'selected_template': selected_template,
            'selected_subject': selected_subject,
            'resume_name': resume_name,
            'days': days,
            'number_of_jobs': number_of_jobs,
            'completed': 0,
            'total': number_of_emails
        }
    jobs.insert_one(job_document)
    return jsonify({"success": True, "message": "Job is Scheduled"}), 200
        
        