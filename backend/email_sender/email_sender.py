# email_utils/email_sender.py
"""
Module to handle sending emails.
"""

import os
import logging
import smtplib
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import pytz





# Set up logging
logger = logging.getLogger(__name__)

def send_email(sender_email, sender_password, recipient_email, subject, message, resume_path):
    """
    Sends an email with an attachment.
    
    Args:
        sender_email (str): Sender's email address.
        sender_password (str): Sender's email password.
        recipient_email (str): Recipient's email address.
        subject (str): Email subject.
        message (str): Email body message.
        company_name (str): Name of the company.
    """
    
    logger.info(f"Sending email to: {recipient_email}")
    print(f"Sending email to: {recipient_email}")
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        print(f"E: -{sender_email}- | -{sender_password}-")
        server.login(sender_email, sender_password)
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        # msg.attach(MIMEText(message, 'plain'))
        msg.attach(MIMEText(message, 'html')) # uncomment if you want your message to be formatted
        
        if resume_path:
            if '\\' in resume_path:
                resume_filename = resume_path.split('\\')[-1]  # Update as necessary
            elif '/' in resume_path:
                resume_filename = resume_path.split('/')[-1]  # Update as necessary
            print("OSPath", os.getcwd(), resume_filename)
            # resume_path = os.path.join("/", resume_filename)
            print("resume_path:", resume_path)
            with open(resume_path, 'rb') as file:
                resume_attachment = MIMEApplication(file.read(), Name=resume_filename)
            resume_attachment['Content-Disposition'] = f'attachment; filename="{resume_filename}"'
            msg.attach(resume_attachment)
        # print("sender_email, recipient_email, msg: ", sender_email, recipient_email, msg)
        res = server.sendmail(sender_email, recipient_email, msg.as_string())
        logger.info(f"Email sent successfully to {recipient_email}: {res}")
        print(f"Email sent successfully to {recipient_email}: {res}")
        server.quit()
        
        return {"success": True}
    except Exception as e:
        logger.error("Error sending email:", exc_info=True)
        return {"error": f"{e}"}
        raise e