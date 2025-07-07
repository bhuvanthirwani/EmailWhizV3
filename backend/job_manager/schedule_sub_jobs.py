import logging_config
import logging
logger = logging.getLogger(__name__)
import copy
from datetime import datetime, timedelta
import traceback
import uuid
import pytz
from db.db import jobs_collection

def schedule_sub_job(job_id):
    try:
        # Get parent job details
        main_job = jobs_collection.find_one({"_id": job_id})
        
        if not main_job:
            return {"error": "Parent job not found"}
        print("main_job", main_job)
        # Extract scheduling parameters
        days_filter = main_job.get('days', [])
        cron_job_name = main_job.get('cron_job_name', 'Send Cold Emails by Automation')
        sub_job_name = main_job.get('sub_job_name', 'Not Available')
        number_of_jobs = main_job.get('number_of_jobs', 1)
        time_str = main_job.get('time', '00:00')
        date_str = main_job.get('date', datetime.now().strftime('%Y-%m-%d'))
        tz = pytz.timezone(main_job.get('timezone', 'UTC'))
        recurring = main_job.get('recurring', False)
        print("days_filter", days_filter)
        print("number_of_jobs", number_of_jobs)
        print("time_str", time_str)
        print("date_str", date_str)
        print("tz", tz)
        print("recurring", recurring)
        # Create base datetime in target timezone
        base_dt = tz.localize(datetime.strptime(
            f"{date_str} {time_str}", 
            "%Y-%m-%d %H:%M"
        ))

        # Day mapping for calculations
        DAY_NUMBERS = {
            'Monday': 0,
            'Tuesday': 1,
            'Wednesday': 2,
            'Thursday': 3,
            'Friday': 4,
            'Saturday': 5,
            'Sunday': 6
        }

        # Create base datetime in target timezone
        base_dt = tz.localize(datetime.strptime(
            f"{date_str} {time_str}", 
            "%Y-%m-%d %H:%M"
        ))

        current_dt = base_dt
        sub_job_ids = []
        scheduled_count = 0
        used_days = set()
        
        print("number_of_jobs", number_of_jobs)
        while scheduled_count < int(number_of_jobs):
            # Get current day name (e.g., "Monday")
            current_day = current_dt.strftime("%A")
            
            # Check if current day matches filter
            if current_day in days_filter:
                used_days.add(current_day)
                scheduled_count += 1
            
            
                # Create sub-job document
                sub_job = copy.deepcopy(main_job)
                print("sub_job", sub_job)
                sub_job.update({
                    '_id': str(uuid.uuid4()),
                    'cron_job_id': job_id,
                    'date': current_dt.strftime('%Y-%m-%d'),
                    'time': current_dt.strftime('%H:%M'),
                    'timezone': str(tz),
                    'action': 'send_cold_emails_by_automation_through_apollo_emails_job',
                    'sub_action': None,
                    'job_name': sub_job_name,
                    'status': 'scheduled',
                    'schedule': 'custom',
                    'job_number': scheduled_count,
                    'created_at': datetime.utcnow(),
                    'latest_log': f'Scheduled for {current_dt}',
                    'highlights': [f'Scheduled for {current_dt}']
                })
                print("sub_job", sub_job)

                # Cleanup parent-specific fields
                for field in ['cron_job_name', 'cron_job_description', 'days', 'recurring']:
                    sub_job.pop(field, None)
                print("111111", sub_job)
                jobs_collection.insert_one(sub_job)
                sub_job_ids.append(sub_job['_id'])
            
            current_dt += timedelta(days=1)

            # Break if we've exhausted all days in non-recurring mode
            if len(used_days) == len(days_filter):
                used_days = set()

        return {
            "success": f"Scheduled {len(sub_job_ids)} jobs",
            "sub_job_ids": sub_job_ids
        }

    except Exception as e:
        traceback.print_exc()
        print("error", e)
        return {"error": f"Scheduling failed: {str(e)}"}