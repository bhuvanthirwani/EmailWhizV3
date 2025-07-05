import concurrent.futures
import time
from datetime import datetime, timedelta
import traceback
from pymongo import MongoClient
import pytz

from job_manager.schedule_sub_jobs import schedule_sub_job
from apollo.cold_emails.automation import send_cold_emails_by_automation_through_apollo_emails_job
from apollo.cold_emails.by_company import send_cold_emails_by_company_through_apollo_emails_job


from db.db import get_users_db, get_user_details, jobs_collection
# # MongoDB Connection
# client = MongoClient('mongodb+srv://shoaibthakur23:Shoaib@emailwhiz.ltjxh42.mongodb.net/')
# db = client["EmailWhiz"]
# jobs_collection = db["jobs"]

class CronJobScheduler:
    def __init__(self, max_workers=6):
        """Initialize and start the scheduler with ThreadPoolExecutor."""
        self.keep_running = False
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.running_jobs = {}  # Track running jobs using job_id

        self.job_functions = {
            "schedule_sub_job": schedule_sub_job,
            "send_cold_emails_by_automation_through_apollo_emails_job": send_cold_emails_by_automation_through_apollo_emails_job,
            "send_cold_emails_by_company_through_apollo_emails_job": send_cold_emails_by_company_through_apollo_emails_job,
            
        }
        
        # # Start the scheduler and monitoring in background threads
        # self.executor.submit(self.scheduler, just_deploy=True, env='production')
        self.executor.submit(self.monitor_scheduler)

    def monitor_scheduler(self):
        """Monitor jobs based on job_updated_at and restart if necessary."""
        while self.keep_running:
            now = datetime.utcnow()
            threshold = timedelta(minutes=2)  # If no update in 2 minutes, restart job

            jobs = jobs_collection.find({"status": "running"})
            for job in jobs:
                job_id = str(job["_id"])
                last_updated = job.get("job_updated_at", datetime.utcnow())

                if now - last_updated > threshold:
                    print(f"Job {job_id} appears to be dead, respawning...")
                    self.spawn_job(job)

            time.sleep(30)

    def scheduler(self, just_deploy=False, env=None):
        """Main scheduler loop that checks for jobs and submits them to ThreadPoolExecutor."""
        scheduler_meta_collection = db["job_scheduler_meta"]
        if just_deploy:
            scheduler_meta_collection.update_one({"identifier": "running_state", "env": env}, {"$set": {"status": "stopped"}})
            return
        while self.keep_running:
            
            running_state = scheduler_meta_collection.find_one({"identifier": "running_state", "env": env})
            
            if running_state.get("status", None) != "running":
                print("Scheduler is not running...")
                self.keep_running = False
                break
            print("Scheduler is running...")
            try:
                job = jobs_collection.find_one({"status": "scheduled"})
                print(f"Jobs: {job}")
                if job:
                    if self.should_execute(job):
                        self.spawn_job(job)  # Submit job execution to ThreadPoolExecutor
                # if jobs:
                #     print(f"Jobs: {len(list(jobs))}")
                #     for job in jobs:
                #         print(f"Job: {job}")
                #         if self.should_execute(job):
                #             self.spawn_job(job)  # Submit job execution to ThreadPoolExecutor
                time.sleep(30)  # Polling interval
            except Exception as e:
                traceback.print_exc()
                print(f"Error in scheduler loop: {e}")
                break

    def spawn_job(self, job):
        """Submit a job to the ThreadPoolExecutor for execution."""
        job_id = str(job["_id"])
        print(f"Spawning Job ID: {job_id}")
        future = self.executor.submit(self.execute_job, job)
        self.running_jobs[job_id] = future

    def should_execute(self, job):
        """Determine if a job should execute based on its schedule."""
        schedule_type = job.get("schedule", None)
        if schedule_type == "now":
            return job["status"] == "scheduled" and job.get("completed", None) == 0
        
        now = datetime.now(pytz.timezone(job["timezone"]))

        

        if schedule_type == "custom":
            scheduled_time = self.get_local_time(job["time"], job["date"], job["timezone"])
            return now >= scheduled_time and job["status"] == "scheduled"

        elif schedule_type == "weekly":
            if now.strftime("%A") in job["days"]:
                scheduled_time = now.replace(hour=int(job["time"].split(":")[0]),
                                             minute=int(job["time"].split(":")[1]),
                                             second=int(job["time"].split(":")[2]))
                return now >= scheduled_time and job["status"] == "scheduled"

        elif schedule_type == "monthly":
            if now.day == int(job["date"].split("-")[2]):
                scheduled_time = now.replace(hour=int(job["time"].split(":")[0]),
                                             minute=int(job["time"].split(":")[1]),
                                             second=int(job["time"].split(":")[2]))
                return now >= scheduled_time and job["status"] == "scheduled"

        return False

    def execute_job(self, job):
        """Execute the job and update MongoDB."""
        try:
            print(f"Executing Job ID: {job['_id']}")
            print(f"Job: {job}")
            action = job["action"]
            print(f"Action: {action}")
            
            job_id = job["_id"]
            print(f"Job ID: {job_id}")
            result = jobs_collection.update_one(
                    {"_id": job_id},
                    {"$set": {
                        "latest_log": "Started",
                        "status": "running",
                        "job_updated_at": job["job_updated_at"]
                    },
                    "$push": {
                        "highlights": "Job Started"
                    }
                    }
                )
            print(f"Result: {result} {result.modified_count}")
            if result.modified_count == 0:
                print(f"Job {job_id} is already running.")
                return
            else:
                if action in self.job_functions:
                    response = self.job_functions[action](job_id)  # Call the corresponding function
                    job["status"] = 'completed'
                    if response.get("success"):
                        job["latest_log"] = f"Job Executed: at {datetime.utcnow()} | Job ID: {job_id}"
                    else:
                        job["status"] = 'error'
                        job["latest_log"] = f"Sub Job Failed: at {datetime.utcnow()} | Job ID: {job_id} | Error: {response['error']}"
                
                    job["job_updated_at"] = datetime.utcnow()  # Update last job update time
                    jobs_collection.update_one(
                        {"_id": job_id},
                        {"$set": {
                            "latest_log": job["latest_log"],
                            "status": job["status"],
                            "job_updated_at": job["job_updated_at"]
                        },
                        "$push": {
                            "highlights": job["latest_log"]
                        }
                        }
                    )
                    if not job.get("recurring", None):
                        job["status"] = "completed" if job["status"] != "error" else "error"
                        job["latest_log"] = f"Cron Job Completed."

                        jobs_collection.update_one(
                            {"_id": job_id},
                            {"$set": {
                                "latest_log": job["latest_log"],
                                "status": job["status"],
                                "job_updated_at": job["job_updated_at"]
                            },
                            "$push": {
                                "highlights": job["latest_log"]
                                }
                            }
                        )
                else:

                    print(f"No function found for action: {action}")
        except Exception as e:
            print(f"Error executing job {job_id}: {e}")
            job["latest_log"] = f"Error executing job {job_id}: {e}"
            job["status"] = "error"
            job["job_updated_at"] = datetime.utcnow()
            jobs_collection.update_one(
                {"_id": job_id},
                {"$set": job}
            )


    def get_local_time(self, time_str, date_str, timezone):
        """Convert time and date strings into a localized datetime object."""
        local_tz = pytz.timezone(timezone)
        naive_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return local_tz.localize(naive_datetime)

    # Example job functions
    def send_cold_emails(self):
        print("Sending cold emails...")

    def generate_report(self):
        print("Generating report...")

    def backup_database(self):
        print("Backing up the database...")

    def stop_scheduler(self, env):
        """Stop the scheduler and shut down ThreadPoolExecutor."""
        self.keep_running = False
        scheduler_meta_collection = db["job_scheduler_meta"]
        scheduler_meta_collection.update_one({"identifier": "running_state", "env": env}, {"$set": {"status": "stopped"}})
        # self.executor.shutdown(wait=True)
        print("Scheduler stopped.")
    
    def start_scheduler(self, env):
        """Start the scheduler and resume ThreadPoolExecutor."""
        self.keep_running = True
        scheduler_meta_collection = db["job_scheduler_meta"]
        scheduler_meta_collection.update_one({"identifier": "running_state", "env": env}, {"$set": {"status": "running"}})
        print("Scheduler started.")
        # env = 'development'
        env = 'production'
        self.executor.submit(self.scheduler, env=env)


# Initialize the scheduler (runs automatically in the background)
cron_job_scheduler = CronJobScheduler(max_workers=6)
