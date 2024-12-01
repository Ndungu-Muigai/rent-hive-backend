import sib_api_v3_sdk
from api import app
from dotenv import load_dotenv
import os

load_dotenv()

configuration=sib_api_v3_sdk.Configuration()
configuration.api_key["api-key"] = os.environ["SENDINBLUE_API_KEY"]
api_instance=sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

def send_login_credentials(first_name, last_name, email, password):
    subject="Login credentials"
    sender={"name": app.app.config["SENDER_NAME"], "email": app.app.config["SENDER_EMAIL"]}
    print(first_name)
    print(last_name)
    print(email)
    print(password)
    print(subject)
    print(sender)
    # email_content=f"""
    # <p>Dear {first_name} {last_name},</p>
    # <p>Your Rent Hive Rental Management System account has been created successfully.</p>
    # <p>Use the login credentials below to login: </p>
    # <h4>Email: {email}</h4>
    # <h4>Password: {password}</h4>
    # <h4>Login Link: <a href='https://rent-hive.vercel.app/' target='_blank'>Rent Hive Rental Management System</a></h4>
    # <b>Kindly do not share your login details</b><br><br>

    # <b>NB:This is an system generated email. Please DO NOT reply to this email thread.</b>
    # """

    # to= [{"name": f"{first_name} {last_name}", "email": email}]

    # send_email=sib_api_v3_sdk.SendSmtpEmail(to=to, html_content=email_content,sender=sender, subject=subject)

    # try:
    #     print("Sending the email")
    #     # Attempt to send the email
    #     api_instance.send_transac_email(send_email)

    #     print("Email sent successfully")

    # except sib_api_v3_sdk.rest.ApiException as e:
    #     # Catch any API-related errors and print/log the error details
    #     print(f"Error sending email to {email}: {e}")
    #     return {"error": "An unexpected error occurred. Please try again later!"}
    # except Exception as e:
    #     # Catch any other errors that may occur
    #     print(f"Unexpected error: {e}")
    #     return {"error": "An unexpected error occurred. Please try again later!"}