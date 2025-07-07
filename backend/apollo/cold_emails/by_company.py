import logging_config  # Ensure centralized logging is configured
import logging
logger = logging.getLogger(__name__)
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
import time
import traceback
from email_sender.email_sender import send_email
from flask import jsonify, request, session

from db.db import get_users_db, get_user_details, jobs_collection

# Media root for file storage
MEDIA_ROOT = 'users'

def send_cold_emails_by_company_through_apollo_emails_job(request, temp_data):
    try:
        selected_subject = temp_data.get("selected_subject", None)
        username = temp_data.get("username", None)
        company_info = temp_data.get("company_info", None)
        job_titles = temp_data.get("job_titles", None)
        locations = temp_data.get("locations", None)
        target_role = temp_data.get("target_role", None)
        selected_template = temp_data.get("selected_template", None)
        resume_name = temp_data.get("resume_name", None)
        time = temp_data.get("time", None)
        date = temp_data.get("date", None)
        timezone = temp_data.get("timezone", None)
        recurring = temp_data.get("recurring", None)
        schedule = temp_data.get("schedule", None)
        details = get_user_details(username)
        users_db = get_users_db(details['db_url'])
        subject_collection = users_db['subjects']
        apollo_emails_sent_history_collection = users_db['apollo_emails_sent_history']
        apollo_emails_collection = users_db['apollo_emails']
        if selected_subject:
                
            temp_subject = subject_collection.find_one({"username": username}, {"_id": 0, "subject_title": 1, "subject_content": 1})
            # print("subject: ", temp_subject)
                
        employees = apollo_emails_collection.find({
            "organization_id": company_info["id"],
            "titles": {"$in": job_titles},
            "country":{"$in": locations},
            "email": {"$exists": True, "$ne": None, "$ne": ""},
            # "email_status": "verified"
            })

        employee_count = apollo_emails_collection.count_documents({
            "organization_id": company_info["id"],
            "titles": {"$in": job_titles},
            "country": {"$in": locations},
            # "email_status": "verified"
        })
        print("employees: ", employees, employee_count)
        # Filter employees whose entries are not in apollo_emails_sent_history for the target_role
        filtered_employees = []
        for employee in employees:
            print("E: ", employee)
            existing_history = apollo_emails_sent_history_collection.find_one({
                "person_id": employee["id"],
                "organization_id": employee["organization_id"],
                "emails.target_role": target_role,
            })
            if not existing_history:
                filtered_employees.append(employee)

        if not filtered_employees:
            return jsonify({"error": f"Unable to send Emails as None Emails are Filtered according to your input or All the Emails for your input have been already sent OR There are No Emails which are Unlocked.", "count": 0}), 400
            
        count = 0
        for employee in filtered_employees:
            receiver_first_name = employee["first_name"]
            receiver_last_name = employee["last_name"]
            employee_email = employee["email"]
            organization_id = employee["organization_id"]
            company_name = company_info["name"]
            subject_details = {
            'first_name': details['first_name'], 
            'last_name': details['last_name'],
            'target_role': target_role, 
            'company_name': company_name
            }
            subject = temp_subject["subject_content"]
            for variable in ['first_name', 'last_name', 'target_role', 'company_name']:
                if variable in subject and variable in subject_details:
                    # print("subject_details[variable]: ", subject_details[variable])
                    subject = subject.replace("{" + variable + "}", subject_details[variable])
                    # print("S: ", subject)
            print("subject2: ", subject)
            # subject = f"[{details['first_name']} {details['last_name']}]: Exploring {target_role} Roles at {company_name}"
            template_path = os.path.join(MEDIA_ROOT, username, 'templates', selected_template)
            with open(template_path, 'r') as f:
                content = f.read()
            resume_path = os.path.join(MEDIA_ROOT, username, 'resumes', resume_name)

            personalized_message = content.format(
                first_name=receiver_first_name,
                last_name=receiver_last_name,
                email=employee_email,
                company_name=company_name,
                designation=target_role,
            )

            send_email(details['gmail_id'], details['gmail_in_app_password'], employee_email, subject, personalized_message, resume_path)
            time.sleep(0.25)
            existing_entry = apollo_emails_sent_history_collection.find_one(
                {"person_id": employee["id"], "organization_id": organization_id}
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
                    {"_id": existing_entry["_id"]},
                    {"$push": {"emails": new_email_entry}}
                )
                print("Entry Exist, We have started pushing.....")
            else:
                # Create a new document if no history exists
                email_history_entry = {
                    "person_id": employee["id"],
                    "receiver_email": employee_email,
                    "company": company_name,
                    "organization_id": organization_id,
                    "emails": [new_email_entry],
                }
                apollo_emails_sent_history_collection.insert_one(email_history_entry)
            count += 1
        
        if(count == 0):
            return jsonify({"error": f"Unable to send Emails for {company_info['name']}", "count": count}), 400

        else:
            return jsonify({"success": f"{count} Emails Sent Successfully", "count": count}), 200
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": f"{exc}"}), 500
    


def send_cold_emails_by_company_through_apollo_emails(request):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    username = data.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400
    company_info = data.get("company_id", None)
    # print("company_id: ", company_info)
    locations = data.get('locations', None)
    cron_job_description = data.get("cron_job_description", None)
    cron_job_name = data.get("cron_job_name", None)
    _time = data.get("time", None)
    date = data.get("date", None)
    timezone = data.get("timezone", None)
    recurring = data.get("recurring", None)
    schedule = data.get("schedule", None)
    number_of_companies = data.get("number_of_companies", 1)

    job_titles = data.get("job_titles", None)
    target_role = data.get("target_role", None)
    selected_template = data.get("selected_template", None)
    selected_subject = data.get("selected_subject", None)
    resume_name = data.get("selected_resume", None)
    # print("loctions, job_titles, target_role, company_info, selected_template, resume_name, selected_subject", locations, job_titles, target_role, company_info, selected_template, resume_name, selected_subject)
    
    
    details = get_user_details(username)
    users_db = get_users_db(details['db_url'])
    jobs = jobs_collection
    existing_job = jobs.find_one({"username": username, "status": "running", "action": "send_cold_emails_by_company"})
    if existing_job:
        return jsonify({
            "error": f"A job of type '{existing_job['id']}' is already running for this user. Please wait for it to complete."
        }), 400
    executor = ThreadPoolExecutor(max_workers=5)
    if schedule == 'now':
        temp_data = {
            'username': username, 
            'company_info': company_info,
            'locations': locations, 
            'job_titles': job_titles,
            'number_of_companies': number_of_companies,
            'cron_job_description': cron_job_description,
            'cron_job_name': cron_job_name,
            'target_role': target_role,
            'selected_template': selected_template,
            'selected_subject': selected_subject,
            'resume_name': resume_name,
            
        }
    elif schedule == 'custom':
        temp_data = {
            'username': username, 
            'company_info': company_info,
            'locations': locations, 
            'job_titles': job_titles,
            'cron_job_description': cron_job_description,
            'cron_job_name': cron_job_name,
            'number_of_companies': number_of_companies,
            'time': _time,
            'date': date,
            'timezone': timezone,
            'recurring': recurring,
            'target_role': target_role,
            'selected_template': selected_template,
            'selected_subject': selected_subject,
            'resume_name': resume_name,
        }
    
    # executor.submit(send_cold_emails_by_company_job, request, temp_data)
    return jsonify({"success": True, "message": "Job has started"}), 200

