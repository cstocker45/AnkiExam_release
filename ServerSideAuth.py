# --- Auth setup ---
SECRET_KEY = "supersecretkey"  # Change this in production!
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Email settings ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "your-email@gmail.com"  # Replace with your Gmail address
SMTP_PASSWORD = "your-16-char-app-password"  # Replace with your App Password from Google
# To get an App Password:
# 1. Go to https://myaccount.google.com/security
# 2. Enable 2-Step Verification if not already enabled
# 3. Go to Security → App Passwords
# 4. Generate a new App Password for "Mail" and your app name
# 5. Copy the 16-character password and paste it here

def send_verification_email(email: str, code: str):
    msg = MIMEText(f"Your verification code is: {code}")
    msg["Subject"] = "Your AnkiExam Verification Code"
    msg["From"] = SMTP_USER
    msg["To"] = email
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, [email], msg.as_string()) 