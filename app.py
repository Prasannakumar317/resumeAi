from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask import send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta
import logging
from fpdf import FPDF

# Lazy load genai to avoid slow imports blocking startup
genai = None

try:
	import PyPDF2
except Exception:
	PyPDF2 = None


import os
from datetime import datetime
import re
import io
try:
	import requests
except Exception:
	requests = None

app = Flask(__name__)
# Use an environment variable for production secret; fallback for local dev
app.secret_key = os.environ.get('SECRET_KEY', 'dev_change_me_to_secure_random')

# Session configuration for security
# Auto-detect production environment
is_production = os.environ.get('ENVIRONMENT', '').lower() == 'production' or 'vercel' in os.environ
app.config['SESSION_COOKIE_SECURE'] = is_production  # True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Debug mode - OFF in production
app.debug = not is_production
print(f"[CONFIG] Production mode: {is_production}, Debug: {app.debug}")

# Enable CSRF protection
csrf = CSRFProtect(app)

# Add CSRF token to all templates
@app.context_processor
def inject_csrf_token():
	"""Make csrf_token() available in all templates"""
	try:
		from flask_wtf.csrf import generate_csrf
		return {'csrf_token': generate_csrf}
	except Exception as e:
		print(f"[CSRF ERROR] Failed to inject CSRF token: {e}")
		return {'csrf_token': lambda: ''}

# Setup logging for authentication
logging.basicConfig(level=logging.INFO)
auth_logger = logging.getLogger('auth')

# Setup Gemini API Key from environment (set in run.ps1) or hardcoded fallback
GEMINI_API_KEY = os.environ.get('GOOGLE_API_KEY', 'AIzaSyD8jU1qowhNywKs8AzJ_J_ACkVpdU3MUaA')

def init_genai():
	"""Initialize Gemini API - called lazily to avoid slow startup"""
	global genai
	if genai is None:
		try:
			import google.generativeai as genai_temp
			genai_temp.configure(api_key=GEMINI_API_KEY)
			genai = genai_temp
			print("[INIT] Gemini API initialized successfully")
		except Exception as e:
			print(f"[INIT WARNING] Failed to initialize Gemini API: {e}")
			genai = False  # Mark as failed so we don't retry

# Database (SQLite for local/dev). For production on Vercel, use PostgreSQL from DATABASE_URL
basedir = os.path.abspath(os.path.dirname(__file__))

# Check for Vercel production database first (PostgreSQL)
database_url = os.environ.get('DATABASE_URL')
if database_url:
	# Vercel provides PostgreSQL URL - use it
	if database_url.startswith('postgres://'):
		database_url = database_url.replace('postgres://', 'postgresql://', 1)
	app.config['SQLALCHEMY_DATABASE_URI'] = database_url
	print(f"[DB] Using production database from DATABASE_URL")
else:
	# Local development - use SQLite
	db_path = os.environ.get('DATABASE_PATH', os.path.join(basedir, 'site.db'))
	db_path_uri = 'sqlite:///' + db_path if not db_path.startswith('sqlite://') else db_path
	app.config['SQLALCHEMY_DATABASE_URI'] = db_path_uri
	print(f"[DB] Using local database: {db_path}")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Uploads folder (used by analyzer)
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Security: limit uploaded file size (5 MB)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Allowed resume extensions
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.doc', '.docx'}

def allowed_file(filename: str) -> bool:
	_, ext = os.path.splitext(filename.lower())
	return ext in ALLOWED_EXTENSIONS


class User(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(150), nullable=False)
	email = db.Column(db.String(150), unique=True, nullable=False, index=True)
	password_hash = db.Column(db.String(255), nullable=False)
	created_at = db.Column(db.DateTime, default=datetime.utcnow)
	last_login = db.Column(db.DateTime)
	is_active = db.Column(db.Boolean, default=True)
	failed_attempts = db.Column(db.Integer, default=0)
	locked_until = db.Column(db.DateTime)

	def set_password(self, password: str):
		"""Hash and store the password"""
		try:
			self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
			print(f"[AUTH] Password hash generated successfully")
		except Exception as e:
			print(f"[AUTH ERROR] Failed to hash password: {e}")
			raise

	def check_password(self, password: str) -> bool:
		"""Verify the provided password against the hash"""
		try:
			if not self.password_hash:
				print(f"[AUTH] No password hash stored for user")
				return False
			return check_password_hash(self.password_hash, password)
		except Exception as e:
			print(f"[AUTH ERROR] Failed to verify password: {e}")
			return False
	
	def is_locked(self) -> bool:
		"""Check if account is locked due to failed login attempts"""
		if self.locked_until and self.locked_until > datetime.utcnow():
			return True
		return False
	
	def record_failed_login(self):
		"""Record a failed login attempt and lock account if needed"""
		self.failed_attempts += 1
		if self.failed_attempts >= 5:
			self.locked_until = datetime.utcnow() + timedelta(minutes=15)
		db.session.commit()
	
	def reset_failed_attempts(self):
		"""Reset failed attempts on successful login"""
		self.failed_attempts = 0
		self.locked_until = None
		self.last_login = datetime.utcnow()
		db.session.commit()


class LoginHistory(db.Model):
	"""Track user login history for security"""
	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
	login_time = db.Column(db.DateTime, default=datetime.utcnow)
	ip_address = db.Column(db.String(45))
	user_agent = db.Column(db.String(255))
	success = db.Column(db.Boolean, default=True)
	
	user = db.relationship('User', backref='login_history')


def is_valid_email(email: str) -> bool:
	return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def is_strong_password(password: str) -> tuple[bool, str]:
	"""Validate password strength"""
	if len(password) < 8:
		return False, "Password must be at least 8 characters long"
	if not re.search(r'[a-z]', password):
		return False, "Password must contain lowercase letters"
	if not re.search(r'[A-Z]', password):
		return False, "Password must contain uppercase letters"
	if not re.search(r'[0-9]', password):
		return False, "Password must contain numbers"
	if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?]', password):
		return False, "Password must contain special characters (!@#$%^&* etc)"
	return True, "Password is strong"


def get_client_ip():
	"""Get client IP address from request"""
	if request.headers.getlist("X-Forwarded-For"):
		return request.headers.getlist("X-Forwarded-For")[0]
	return request.remote_addr


def login_required(f):
	"""Decorator to protect routes that require login"""
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user_id' not in session:
			flash('Please log in to access this page', 'error')
			return redirect(url_for('login'))
		
		# Check if user still exists and is active
		user = User.query.get(session['user_id'])
		if not user or not user.is_active:
			session.clear()
			flash('Your account is no longer available', 'error')
			return redirect(url_for('login'))
		
		return f(*args, **kwargs)
	return decorated_function


def generate_resume_pdf(name: str, email: str, phone: str, summary: str, education: str, experience: str, achievements: str, skills: str, declaration: str, template: str = 'professional') -> bytes:
	"""Generate a resume PDF using FPDF."""
	if FPDF is None:
		print("ERROR: FPDF library not loaded!")
		return None
	
	try:
		# Process inputs
		name = str(name or "Resume").strip()
		email = str(email or "").strip()
		phone = str(phone or "").strip()
		summary = str(summary or "").strip()
		education_list = [x.strip() for x in str(education or "").split('\n') if x.strip()]
		experience_list = [x.strip() for x in str(experience or "").split('\n\n') if x.strip()]
		if not experience_list and experience:
			experience_list = [x.strip() for x in str(experience or "").split('\n') if x.strip()]
		achievements_list = [x.strip() for x in str(achievements or "").split('\n') if x.strip()]
		skills_list = [x.strip() for x in str(skills or "").split(',') if x.strip()]
		declaration = str(declaration or "").strip()
		
		pdf = FPDF(format='A4')
		pdf.add_page()
		pdf.set_auto_page_break(auto=True, margin=15)
		
		# Set styling according to templates
		if template == 'modern':
			# Draw a colored sidebar
			pdf.set_fill_color(102, 126, 234)
			pdf.rect(0, 0, 60, 297, "F")
			
			# Sidebar Content (Name & Info)
			pdf.set_text_color(255, 255, 255)
			
			# Name
			pdf.set_y(20)
			pdf.set_x(5)
			pdf.set_font("Arial", "B", 18)
			pdf.multi_cell(50, 8, name, align="L")
			
			pdf.set_font("Arial", "", 10)
			pdf.set_y(50)
			pdf.set_x(5)
			if email:
				pdf.multi_cell(50, 5, "Email:\n" + email)
				pdf.ln(2)
			pdf.set_x(5)
			if phone:
				pdf.multi_cell(50, 5, "Phone:\n" + phone)
				pdf.ln(5)
				
			if skills_list:
				pdf.set_x(5)
				pdf.set_font("Arial", "B", 11)
				pdf.cell(50, 8, "SKILLS", new_x="LMARGIN", new_y="NEXT")
				pdf.set_font("Arial", "", 10)
				for skill in skills_list:
					pdf.set_x(5)
					pdf.multi_cell(50, 5, f"- {skill}")
			
			# Main Content Margin
			left_margin = 65
			pdf.set_y(20)
			pdf.set_left_margin(left_margin)
			
			def print_section(title, content_list, bullet=False, is_summary=False):
				if not content_list and not is_summary: return
				pdf.set_text_color(102, 126, 234)
				pdf.set_font("Arial", "B", 12)
				pdf.cell(0, 8, title.upper(), new_x="LMARGIN", new_y="NEXT")
				pdf.set_draw_color(102, 126, 234)
				pdf.line(left_margin, pdf.get_y(), 200, pdf.get_y())
				pdf.ln(2)
				pdf.set_text_color(51, 51, 51)
				pdf.set_font("Arial", "", 10)
				
				if is_summary and content_list:
					pdf.multi_cell(0, 5, content_list)
					pdf.ln(5)
					return
				
				for item in content_list:
					clean = str(item).replace("<br/>", "")
					if bullet:
						pdf.multi_cell(0, 5, chr(149) + " " + clean)
					else:
						pdf.multi_cell(0, 5, clean)
					pdf.ln(2)
				pdf.ln(3)

			print_section("Professional Summary", summary, is_summary=True)
			print_section("Experience", experience_list)
			print_section("Education", education_list)
			print_section("Achievements", achievements_list, bullet=True)
			
		elif template == 'creative':
			pdf.set_text_color(245, 158, 11)
			pdf.set_font("Helvetica", "B", 24)
			pdf.cell(0, 10, name.upper(), align="C", new_x="LMARGIN", new_y="NEXT")
			
			pdf.set_text_color(100, 100, 100)
			pdf.set_font("Helvetica", "", 11)
			contact = []
			if email: contact.append(email)
			if phone: contact.append(phone)
			if contact:
				pdf.cell(0, 6, " | ".join(contact), align="C", new_x="LMARGIN", new_y="NEXT")
			
			pdf.set_draw_color(245, 158, 11)
			pdf.line(10, pdf.get_y(), 200, pdf.get_y())
			pdf.ln(8)
			
			def print_section(title, content_list, bullet=False, is_summary=False):
				if not content_list and not is_summary: return
				pdf.set_text_color(245, 158, 11)
				pdf.set_font("Helvetica", "B", 14)
				pdf.cell(0, 8, str(title), new_x="LMARGIN", new_y="NEXT")
				pdf.set_text_color(60, 60, 60)
				pdf.set_font("Helvetica", "", 11)
				
				if is_summary and content_list:
					pdf.multi_cell(0, 6, str(content_list))
					pdf.ln(4)
					return
					
				for item in content_list:
					clean = str(item).replace("<br/>", "")
					if bullet:
						pdf.multi_cell(0, 6, chr(149) + " " + clean)
					else:
						pdf.multi_cell(0, 6, clean)
					pdf.ln(2)
				pdf.ln(4)
				
			print_section("Summary", summary, is_summary=True)
			print_section("Experience", experience_list)
			print_section("Education", education_list)
			if skills_list:
				print_section("Skills", [", ".join(skills_list)], is_summary=True)
			print_section("Achievements", achievements_list, bullet=True)

		else: # Professional / default
			pdf.set_text_color(40, 50, 100)
			pdf.set_font("Times", "B", 22)
			pdf.cell(0, 12, name, align="C", new_x="LMARGIN", new_y="NEXT")
			
			pdf.set_text_color(80, 80, 80)
			pdf.set_font("Times", "I", 11)
			contact = []
			if email: contact.append(email)
			if phone: contact.append(phone)
			if contact:
				pdf.cell(0, 6, " | ".join(contact), align="C", new_x="LMARGIN", new_y="NEXT")
			
			pdf.set_draw_color(150, 150, 200)
			pdf.line(15, pdf.get_y()+2, 195, pdf.get_y()+2)
			pdf.ln(8)
			
			def print_section(title, content_list, bullet=False, is_summary=False):
				if not content_list and not is_summary: return
				pdf.set_text_color(40, 50, 100)
				pdf.set_font("Times", "B", 13)
				pdf.cell(0, 8, str(title).upper(), new_x="LMARGIN", new_y="NEXT")
				pdf.set_draw_color(200, 200, 200)
				pdf.line(15, pdf.get_y(), 195, pdf.get_y())
				pdf.ln(3)
				pdf.set_text_color(30, 30, 30)
				pdf.set_font("Times", "", 11)
				
				if is_summary and content_list:
					pdf.multi_cell(0, 6, str(content_list))
					pdf.ln(4)
					return
					
				for item in content_list:
					clean = str(item).replace("<br/>", "")
					if bullet:
						pdf.multi_cell(0, 6, chr(149) + " " + clean)
					else:
						pdf.multi_cell(0, 6, clean)
					pdf.ln(2)
				pdf.ln(4)
				
			print_section("Professional Summary", summary, is_summary=True)
			print_section("Experience", experience_list)
			print_section("Education", education_list)
			if skills_list:
				print_section("Technical Skills", [", ".join(skills_list)], is_summary=True)
			print_section("Achievements", achievements_list, bullet=True)
			
		if declaration:
			pdf.ln(10)
			pdf.set_font("Arial", "I", 9)
			pdf.set_text_color(120, 120, 120)
			pdf.multi_cell(0, 5, declaration, align="C")

		# FPDF dest='S' returns a string in Python 3, which needs to be encoded to bytes
		pdf_string = pdf.output(dest='S')
		if isinstance(pdf_string, str):
			return pdf_string.encode('latin-1')
		return pdf_string

	except Exception as e:
		print(f"PDF generation error (FPDF): {str(e)}")
		import traceback
		traceback.print_exc()
		return None


# Database initialization is handled by the run scripts or the Flask CLI; avoid
# creating tables at import-time in case of test/import scenarios.


@app.route('/status')
def status():
	"""Health check and diagnostics endpoint"""
	try:
		db_status = "OK"
		try:
			# Try to query the database
			user_count = User.query.count()
			db_status = f"OK (Users: {user_count})"
		except Exception as de:
			db_status = f"ERROR: {str(de)[:100]}"
		
		return jsonify({
			'status': 'healthy',
			'database': db_status,
			'version': '1.0',
			'environment': 'production' if is_production else 'development',
			'features': ['authentication', 'resume_builder', 'analyzer', 'chat']
		}), 200
	except Exception as e:
		return jsonify({
			'status': 'error',
			'error': str(e)
		}), 500


@app.route('/debug')
def debug():
	"""Debug endpoint for Vercel deployment issues"""
	debug_info = {
		'environment': 'production' if is_production else 'development',
		'has_secret_key': bool(os.environ.get('SECRET_KEY')),
		'has_database_url': bool(os.environ.get('DATABASE_URL')),
		'database_type': 'PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite',
		'csrf_enabled': True,
		'session_secure': app.config.get('SESSION_COOKIE_SECURE'),
		'session_samesite': app.config.get('SESSION_COOKIE_SAMESITE'),
	}
	
	try:
		debug_info['database_connection'] = 'OK'
		User.query.count()
	except Exception as e:
		debug_info['database_connection'] = f'FAILED: {str(e)[:100]}'
	
	return jsonify(debug_info)


@app.route('/')
def index():
	return render_template('welcome.html')


@app.route('/dashboard')
@login_required
def dashboard():
	user = User.query.get(session['user_id'])
	return render_template('index.html', user=user)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
	try:
		if request.method == 'POST':
			name = request.form.get('name', '').strip()
			email = request.form.get('email', '').strip().lower()
			password = request.form.get('password', '')
			confirm_password = request.form.get('confirm_password', '')
			
			print(f"[SIGNUP] Attempt for email: {email}")

			# Validation
			if not name or not email or not password or not confirm_password:
				flash('Please fill all required fields', 'error')
				return redirect(url_for('signup'))

			if not is_valid_email(email):
				flash('Invalid email address', 'error')
				return redirect(url_for('signup'))

			if password != confirm_password:
				flash('Passwords do not match', 'error')
				return redirect(url_for('signup'))

			is_strong, msg = is_strong_password(password)
			if not is_strong:
				flash(msg, 'error')
				return redirect(url_for('signup'))

			try:
				existing = User.query.filter_by(email=email).first()
				if existing:
					flash('Email already registered. Please log in.', 'error')
					return redirect(url_for('login'))
			except Exception as e:
				print(f"[SIGNUP ERROR] Database query failed: {e}")
				flash('Database error. Please try again.', 'error')
				return redirect(url_for('signup'))

			# Create new user
			try:
				user = User(name=name, email=email, is_active=True)
				user.set_password(password)
				print(f"[SIGNUP] Creating user: {email}")
				
				db.session.add(user)
				db.session.commit()
				print(f"[SIGNUP] User created successfully: {email}")
				auth_logger.info(f"New account created: {email}")
				
				# Auto-login the user
				session.permanent = True
				session['user_id'] = user.id
				session['user_name'] = user.name
				session['user_email'] = user.email
				
				try:
					login_history = LoginHistory(
						user_id=user.id,
						ip_address=get_client_ip(),
						user_agent=request.headers.get('User-Agent', '')[:255],
						success=True
					)
					db.session.add(login_history)
					db.session.commit()
				except Exception as he:
					print(f"[SIGNUP] History log error: {he}")
					
				flash(f'Account created successfully! Welcome, {user.name}!', 'success')
				return redirect(url_for('dashboard'))
			except Exception as e:
				db.session.rollback()
				print(f"[SIGNUP ERROR] Failed to create user {email}: {e}")
				import traceback
				traceback.print_exc()
				auth_logger.error(f"Signup error for {email}: {str(e)}")
				flash('An error occurred creating your account', 'error')
				return redirect(url_for('signup'))

		return render_template('signup.html')
	except Exception as e:
		print(f"[SIGNUP CRITICAL ERROR] {type(e).__name__}: {e}")
		import traceback
		traceback.print_exc()
		flash('An error occurred. Please try again.', 'error')
		return redirect(url_for('signup'))


@app.route('/login', methods=['GET', 'POST'])
def login():
	try:
		if request.method == 'POST':
			email = request.form.get('email', '').strip().lower()
			password = request.form.get('password', '')
			print(f"[LOGIN] Attempt for email: {email}")

			if not email or not password:
				flash('Please provide both email and password', 'error')
				return redirect(url_for('login'))

			try:
				user = User.query.filter_by(email=email).first()
				print(f"[LOGIN] User found: {user is not None}")
			except Exception as e:
				print(f"[LOGIN ERROR] Database query failed: {e}")
				flash('Database error. Please try again.', 'error')
				return redirect(url_for('login'))
				
				# Check if account is locked
			if user and user.is_locked():
				flash('Account locked. Try again in 15 minutes.', 'error')
				auth_logger.warning(f"Login on locked account: {email}")
				return redirect(url_for('login'))

			# Check credentials
			if not user or not user.check_password(password):
				print(f"[LOGIN] Invalid credentials for {email}")
				if user:
					user.record_failed_login()
					db.session.commit()
					
					try:
						login_history = LoginHistory(
							user_id=user.id,
							ip_address=get_client_ip(),
							user_agent=request.headers.get('User-Agent', '')[:255],
							success=False
						)
						db.session.add(login_history)
						db.session.commit()
					except Exception as he:
						print(f"[LOGIN] History log error: {he}")
					
				flash('Invalid email or password', 'error')
				return redirect(url_for('login'))

			# Successful login
			if not user.is_active:
				flash('Account inactive', 'error')
				return redirect(url_for('login'))

			print(f"[LOGIN] Password verified for {email}")
			user.reset_failed_attempts()
			db.session.commit()
			
			try:
				login_history = LoginHistory(
					user_id=user.id,
					ip_address=get_client_ip(),
					user_agent=request.headers.get('User-Agent', '')[:255],
					success=True
				)
				db.session.add(login_history)
				db.session.commit()
			except Exception as he:
				print(f"[LOGIN] History log error: {he}")

			# Set session
			try:
				session.permanent = True
				session['user_id'] = user.id
				session['user_name'] = user.name
				session['user_email'] = user.email
				print(f"[LOGIN] Session created for user_id: {user.id}")
			except Exception as se:
				print(f"[LOGIN] Session error: {se}")
				flash('Session error', 'error')
				return redirect(url_for('login'))
				
			auth_logger.info(f"Successful login: {email}")
			flash(f'Welcome back, {user.name}!', 'success')
			return redirect(url_for('dashboard'))

		return render_template('login.html')
	except Exception as e:
		print(f"[LOGIN CRITICAL ERROR] {type(e).__name__}: {e}")
		import traceback
		traceback.print_exc()
		flash('An error occurred. Please try again.', 'error')
		return redirect(url_for('login'))


@app.route('/logout')
def logout():
	user_email = session.get('user_email', 'unknown')
	session.clear()
	auth_logger.info(f"User logged out: {user_email}")
	flash('Logged out successfully', 'info')
	return redirect(url_for('index'))

@app.route('/preview', methods=['POST'])
def preview():
	"""Render an HTML preview of the resume based on submitted form data.

	The builder form posts raw text blobs; split them into lists here so the
	Jinja templates can iterate cleanly and apply per-template ordering.
	"""
	name = request.form.get('name', '').strip()
	email = request.form.get('email', '').strip()
	phone = request.form.get('phone', '').strip()
	summary = request.form.get('summary', '').strip()
	declaration = request.form.get('declaration', '').strip()

	experience = '\n'.join([e.strip() for e in request.form.getlist('experience') if e.strip()])
	education = '\n'.join([e.strip() for e in request.form.getlist('education') if e.strip()])
	achievements = '\n'.join([a.strip() for a in request.form.getlist('achievements') if a.strip()])
	skills = ', '.join([s.strip() for s in request.form.getlist('skills') if s.strip()])
	template_choice = request.form.get('template', 'professional')

	# convert the multiline/CSV strings into python lists for Jinja iteration
	experience_list = [line for line in experience.split('\n') if line]
	education_list = [line for line in education.split('\n') if line]
	achievements_list = [line for line in achievements.split('\n') if line]
	skills_list = [s.strip() for s in skills.split(',') if s.strip()]

	return render_template(
		f'preview_{template_choice}.html',
		name=name, email=email, phone=phone, summary=summary,
		experience_list=experience_list, education_list=education_list,
		achievements_list=achievements_list, skills_list=skills_list,
		declaration=declaration
	)

@app.route('/builder', methods=['GET', 'POST'])
def builder():
	message = None
	download = None
	if request.method == 'POST':
		try:
			name = request.form.get('name', '').strip()
			email = request.form.get('email', '').strip()
			phone = request.form.get('phone', '').strip()
			summary = request.form.get('summary', '').strip()
			declaration = request.form.get('declaration', '').strip()

			if not name:
				message = 'Name is required.'
				return render_template('builder.html', message=message)

			# Get all values for fields that can have multiple entries
			experience_list = request.form.getlist('experience')
			experience = '\n'.join([e.strip() for e in experience_list if e.strip()])
			
			education_list = request.form.getlist('education')
			education = '\n'.join([e.strip() for e in education_list if e.strip()])
			
			achievements_list = request.form.getlist('achievements')
			achievements = '\n'.join([a.strip() for a in achievements_list if a.strip()])
			
			skills_list = request.form.getlist('skills')
			skills = ', '.join([s.strip() for s in skills_list if s.strip()])

			print(f"\n--- Resume Data Received ---")
			print(f"Name: {name}")
			print(f"Email: {email}")
			print(f"Phone: {phone}")
			print(f"Summary: {summary[:50]}..." if summary else "Summary: (empty)")
			print(f"Experience entries: {len(experience_list)}")
			print(f"Education entries: {len(education_list)}")
			print(f"Achievements entries: {len(achievements_list)}")
			print(f"Skills entries: {len(skills_list)}")

			template_choice = request.form.get('template', 'professional')
			print(f"Template selected: {template_choice}")
			# Generate PDF resume
			pdf_content = generate_resume_pdf(name, email, phone, summary, education, experience, achievements, skills, declaration, template=template_choice)
			
			if pdf_content is None:
				message = 'Failed to generate PDF. Please check your input and try again.'
				print(f"ERROR: PDF content is None after generation attempt")
				return render_template('builder.html', message=message)
			
			# Save PDF file to disk for records
			safe_name = secure_filename(name) or 'resume'
			timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
			filename = f"{safe_name}_{template_choice}_{timestamp}.pdf"
			save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
			try:
				with open(save_path, 'wb') as fh:
					fh.write(pdf_content)
				message = f"✓ {template_choice.upper()} template resume created successfully!"
				download = filename
				print(f"✓ Resume saved: {filename} ({template_choice} template)")
			except Exception as e:
				print(f"ERROR saving PDF to disk: {e}")
				message = f"{template_choice.upper()} template resume generated, but saving failed: {e}"
			
			# Return PDF bytes directly to avoid any disk-read mismatch
			try:
				from flask import send_file
				buf = io.BytesIO(pdf_content)
				buf.seek(0)
				print(f"[DOWNLOAD] sending {filename} ({template_choice} template)")
				resp = send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)
				# prevent caching by browsers/proxies
				resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
				return resp
			except Exception as e:
				print(f"ERROR sending PDF in-memory: {e}")
				# Fall back to offering the download link in page
				message = f"{message} (saved, but automatic download failed)"
				
		except Exception as e:
			message = f'Error: {str(e)}'
			print(f"ERROR in builder route: {str(e)}")
			import traceback
			traceback.print_exc()
	
	return render_template('builder.html', message=message, download=download)


@app.route('/download/<path:filename>')
def download_file(filename):
	# Serve saved resumes from uploads folder
	return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


@app.route('/analyzer', methods=['GET', 'POST'])
def analyzer():
	result = None
	if request.method == 'POST':
		f = request.files.get('resume')
		role = request.form.get('role', 'Data Scientist')
		if f and f.filename:
			if not allowed_file(f.filename):
				result = 'File type not allowed.'
			else:
				filename = secure_filename(f.filename)
				save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
				f.save(save_path)
				# extract text with diagnostic logging
				text = ''
				_, ext = os.path.splitext(filename.lower())
				print(f"[ANALYZER] Processing: {filename}, Role: {role}")
				try:
					if ext == '.txt':
						with open(save_path, 'r', encoding='utf-8', errors='ignore') as fh:
							text = fh.read()
					elif ext == '.pdf' and PyPDF2 is not None:
						with open(save_path, 'rb') as fh:
							reader = PyPDF2.PdfReader(fh)
							pages = []
							for p in reader.pages:
								try:
									txt = p.extract_text()
									if txt:
										pages.append(txt)
								except Exception as pe:
									print(f"[ANALYZER] Page extraction error: {pe}")
							text = '\n'.join(pages)
					else:
						text = ''
				except Exception as te:
					print(f"[ANALYZER] Text extraction failed: {te}")
					text = ''
				
				print(f"[ANALYZER] Extracted text size: {len(text.strip())} characters")
				if not text.strip():
					flash("Warning: We couldn't read any text from your resume. Please check if it's a scanned PDF or a different file type.", "error")

				# Use Gemini for deep analysis
				init_genai()
				if genai and text:
					prompt = f"""
You are an expert ATS (Applicant Tracking System) and Senior Technical Recruiter.
Analyze the following resume against the role of "{role}".

Return a strictly formatted JSON object with the exact following structure. Do NOT wrap the JSON in markdown code blocks, just return the raw JSON string:
{{
	"role_matching": "A 2-3 sentence summary of how well the candidate fits the {role} role.",
	"keyword_analysis": {{
		"matched": ["list", "of", "matched", "keywords"],
		"missing": {{
			"core_skills": ["list", "of", "missing", "must", "have", "core", "skills"],
			"secondary_skills": ["list", "of", "missing", "nice", "to", "have", "skills"],
			"tools_and_ecosystem": ["list", "of", "missing", "tools", "and", "frameworks"]
		}}
	}},
	"experience_analysis": {{
		"alignment": "Paragraph evaluating their experience alignment.",
		"suggestions": ["List", "of", "actionable", "suggestions"]
	}},
	"project_review": ["If projects exist: suggest adding their tech stack, measurable outcomes, and GitHub links", "If NO projects exist: critically suggest 3-4 specific projects they should build"],
	"education_review": "Observation about their education and certifications.",
	"optimization": ["Formatting or phrasing suggestions to improve readability"],
	"match_breakdown": {{
		"skills_match": {{"score": 18, "maximum": 20}},
		"experience_relevance": {{"score": 12, "maximum": 15}},
		"projects_quality": {{"score": 4, "maximum": 5}},
		"ats_compatibility": {{"score": 35, "maximum": 40}},
		"keyword_optimization": {{"score": 8, "maximum": 10}},
		"impact_and_metrics": {{"score": 7, "maximum": 10}}
	}},
	"score_explanation": "A one sentence explanation of why this score was given.",
	"roadmap": {{
		"title": "Personalized Roadmap to Become a {role}",
		"steps": [
			{{
				"name": "Step 1: Core Fundamentals",
				"duration": "2-3 Weeks",
				"tasks": ["Task 1", "Task 2"]
			}}
		],
		"estimated_readiness": "8-12 Weeks"
	}},
	"bullet_rewrites": [
		{{
			"original": "Worked on frontend",
			"suggested": "Developed responsive UI components using React and Tailwind CSS, improving page load speed by 30%.",
			"improvement_reason": "Needs measurable metrics and stronger action verbs."
		}}
	],
	"ats_optimization": [
		{{
			"check_name": "Quantified Achievements",
			"status": true,
			"feedback": "Great use of percentages and numbers in experience bullets."
		}},
		{{
			"check_name": "Missing Technical Summary",
			"status": false,
			"feedback": "Consider adding a professional summary at the top."
		}}
	]
}}

Resume Text:
{text}
"""
					try:
						model = genai.GenerativeModel('gemini-2.0-flash')
						response = model.generate_content(prompt)
						# More robust JSON extraction
						text_resp = response.text.strip()
						# Find the first { and last } to extract JSON even if there's surrounding text
						start_idx = text_resp.find('{')
						end_idx = text_resp.rfind('}')
						if start_idx != -1 and end_idx != -1:
							json_str = text_resp[start_idx:end_idx+1]
						else:
							json_str = text_resp.replace('```json', '').replace('```', '').strip()
						
						import json
						result = json.loads(json_str)
						result['role'] = role
						result['is_ai_analysis'] = True
						
						# Calculate total score from breakdown with more robust parsing
						total_score = 0
						if 'match_breakdown' in result:
							for key, value in result['match_breakdown'].items():
								if isinstance(value, dict) and 'score' in value:
									try:
										# Handle cases where score might be a string like "8" or a float
										s_val = str(value['score']).replace('%', '').strip()
										total_score += int(float(s_val))
									except (ValueError, TypeError):
										pass
						
						# If breakdown total is still 0, check if there's a top-level match_score
						if total_score == 0 and 'match_score' in result:
							try:
								total_score = int(float(str(result['match_score']).replace('%', '')))
							except (ValueError, TypeError):
								pass

						result['match_score'] = total_score
					except Exception as e:
						print(f"[ANALYZER ERROR] Gemini AI analysis failed or returned invalid JSON: {e}")
						result = None
				
				# Fallback if AI fails or triggers rate limits
				if not result:
					ROLE_KEYWORDS = {
						'Data Scientist': ['python','machine learning','statistics','pandas','numpy','model','data','analysis','deep learning','regression'],
						'Frontend Developer': ['javascript','react','css','html','frontend','typescript','vue','angular','ui','ux'],
						'Backend Developer': ['python','java','node','api','django','flask','sql','database','backend','rest'],
						'DevOps Engineer': ['docker','kubernetes','ci/cd','aws','terraform','ansible','monitoring','sre','jenkins'],
						'Product Manager': ['roadmap','stakeholder','product','metrics','agile','scrum','user research','roadmap']
					}
					keywords = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS['Data Scientist'])
					text_l = (text or '').lower()
					
					# Improved fallback matching (case-insensitive and whitespace aware)
					matched = [kw for kw in keywords if kw.lower() in text_l]
					missing_flat = [kw for kw in keywords if kw.lower() not in text_l]
					
					# Calculate base score from keywords (weighted at 60 points max)
					kw_score = (len(matched) / max(1, len(keywords))) * 60
					
					# Bonus for overall content length and presence of metrics
					bonus = 0
					if len(text_l) > 200: bonus += 10 # Base length
					if re.search(r'\d+%|\$\d+|\d+x', text_l): bonus += 10 # Impact metrics
					
					# Baseline score for having standard resume sections
					for section in ['education', 'experience', 'project', 'skills', 'contact']:
						if section in text_l: bonus += 4
					
					# Ensure a floor of 5% for any readable text, capped at 98% for fallback
					score = min(98, max(5, int(kw_score + bonus)) if text_l.strip() else 0)
					if score >= 60:
						suggestion = 'Resume looks suitable for this role. Consider adding more quantifiable achievements if possible.'
					else:
						suggestion = 'Tailor your resume to the role: add or emphasize skills: ' + ', '.join(missing_flat[:6]) + '. Also highlight relevant projects and measurable outcomes.'
					
					# Split missing into three categories for fallback
					third = max(1, len(missing_flat) // 3)
					missing_categorized = {
						"core_skills": missing_flat[:third],
						"secondary_skills": missing_flat[third:third*2],
						"tools_and_ecosystem": missing_flat[third*2:]
					}

					# Construct a synthetic breakdown for fallback
					base_ratio = len(matched) / max(1, len(keywords))
					breakdown = {
						"skills_match": {"score": int(base_ratio * 20), "maximum": 20},
						"experience_relevance": {"score": int(base_ratio * 15), "maximum": 15},
						"projects_quality": {"score": int(base_ratio * 5), "maximum": 5},
						"ats_compatibility": {"score": int(base_ratio * 40), "maximum": 40},
						"keyword_optimization": {"score": int(base_ratio * 10), "maximum": 10},
						"impact_and_metrics": {"score": int(base_ratio * 10), "maximum": 10},
					}
					
					# Recalculate exact total from the synthetic breakdown
					score = sum(item['score'] for item in breakdown.values())
					
					# Construct a synthetic roadmap
					dummy_roadmap = {
						"title": f"Personalized Roadmap to Become a {role}",
						"steps": [
							{
								"name": "Step 1: Enhance Missing Skills",
								"duration": "1-2 Weeks",
								"tasks": [f"Learn {kw}" for kw in missing_flat[:3]]
							},
							{
								"name": "Step 2: Build Relevant Projects",
								"duration": "3-4 Weeks",
								"tasks": ["Implement a portfolio project", "Add measurable metrics to resume"]
							}
						],
						"estimated_readiness": "4-6 Weeks"
					}
					
					# Construct synthetic bullet rewrites
					dummy_rewrites = [
						{
							"original": "Did some coding and built a feature.",
							"suggested": "Architected and implemented a scalable feature that increased user engagement by 15%.",
							"improvement_reason": "Used strong action verbs and quantifiable metrics."
						}
					]

					# Construct synthetic ATS optimization checks
					has_summary = 'summary' in text_l or 'profile' in text_l or 'objective' in text_l
					has_github = 'github.com' in text_l
					has_portfolio = has_github or 'portfolio' in text_l or '.com' in text_l
					has_metrics = bool(re.search(r'\d+%|\$\d+|\d+x', text_l))
					word_count = len(text.split())
					good_length = 300 < word_count < 1000
					length_feedback = "Resume is a good length." if good_length else ("Resume might be too short." if word_count <= 300 else "Resume might be too long. Consider trimming.")

					ats_checks = [
						{
							"check_name": "Quantified Achievements",
							"status": has_metrics,
							"feedback": "Good use of metrics to drive impact." if has_metrics else "Missing quantifiable metrics (%, $, etc.) in bullet points."
						},
						{
							"check_name": "Technical Summary",
							"status": has_summary,
							"feedback": "Professional summary detected." if has_summary else "Consider adding a short professional summary at the top."
						},
						{
							"check_name": "Keyword Density",
							"status": score > 50,
							"feedback": f"Strong alignment with {role} keywords." if score > 50 else f"Poor keyword density. Specifically add: {', '.join(missing_flat[:3])}."
						},
						{
							"check_name": "Appropriate Length",
							"status": good_length,
							"feedback": length_feedback
						},
						{
							"check_name": "Portfolio/GitHub Links",
							"status": has_portfolio,
							"feedback": "Relevant links detected." if has_portfolio else "Missing a link to your GitHub or portfolio."
						}
					]
					
					# Construct Synthetic Project Mentoring
					if 'project' in text_l or 'projects' in text_l:
						dummy_projects = [
							"Projects detected. Consider explicitly listing the tech stack used for each.",
							"Add measurable outcomes (e.g., 'reduced load time by 15%') to your projects.",
							"Ensure you include active GitHub repository links or live demo URLs."
						]
					else:
						dummy_projects = [
							"No projects detected on your resume. We recommend building the following:",
							"1. Build a functional Todo App (React + Local Storage)",
							"2. Develop a Weather App (API Integration)",
							"3. Create an E-commerce UI Clone to show off styling skills"
						]

					result = {
						'is_ai_analysis': False,
						'role': role,
						'score': score,
						'matched': matched,
						'missing': missing_categorized,
						'suggestion': suggestion,
						'match_breakdown': breakdown,
						'roadmap': dummy_roadmap,
						'bullet_rewrites': dummy_rewrites,
						'ats_optimization': ats_checks,
						'project_review': dummy_projects
					}
		else:
			result = 'No file selected.'
	return render_template('analyzer_v2.html', result=result)


@app.route('/chat', methods=['POST'])
@csrf.exempt
def chat():
	"""Handle chat messages with Google Gemini"""
	try:
		data = request.get_json() or {}
		message = data.get('message', '').strip()
		context = data.get('context', '')
		resume_text = data.get('resume', '').strip()
		
		if not message:
			return jsonify({"response": "I didn't receive a message."}), 400
			
		init_genai()
		if not genai:
			return jsonify({"response": "AI capabilities are currently unavailable (API not configured). Please check back later."}), 503
			
		# System prompt (allows answering ANY question)
		sys_prompt = (
			"You are Resume AI, a helpful AI assistant. "
			"You can answer any question the user asks. "
			"If the question is about resumes, careers, jobs, or skills, provide expert resume and career advice. "
			"If resume context is provided, use it to give personalized suggestions. "
			"Always respond clearly, helpfully, and concisely."
		)

		# Construct prompt
		prompt_parts = []
		prompt_parts.append(sys_prompt + "\n\n")

		if resume_text:
			prompt_parts.append(f"Context (User's Resume Data):\n{resume_text}\n\n")
		
		if context:
			prompt_parts.append(f"User is currently on the '{context}' page.\n\n")
			
		prompt_parts.append(f"User: {message}\nAI:")

		full_prompt = "".join(prompt_parts)

		model = genai.GenerativeModel('gemini-1.5-pro')

		try:
			response = model.generate_content(full_prompt)

			# Safely extract response text
			text = ""
			if response and hasattr(response, "text") and response.text:
				text = response.text.strip()

			if not text:
				text = "I'm sorry, I couldn't generate a response. Please try asking again."

			# Clean markdown formatting if present
			text = text.replace('```json', '').replace('```', '').strip()

			return jsonify({"response": text})

		except Exception as api_err:
			error_str = str(api_err).lower()

			if '429' in error_str or 'quota' in error_str:
				return jsonify({"response": "I'm currently receiving too many requests. Please try again in an hour."})
			else:
				raise api_err
		
	except Exception as e:
		print(f"[CHAT ERROR] {e}")
		return jsonify({
			"error": str(e),
			"response": "Sorry, I encountered an error while processing your request."
		}), 500

@app.route('/ai_resume', methods=['POST'])
@csrf.exempt
def ai_resume():
	"""Simple on-device resume generator and feedback engine.
	Expects JSON payload with: name, email, phone, summary, education,
	experience, skills (comma-separated), job_description.
	Returns JSON with `resume_html` and `feedback`.
	"""
	data = request.get_json() or {}
	name = (data.get('name') or '').strip()
	email = (data.get('email') or '').strip()
	phone = (data.get('phone') or '').strip()
	summary = (data.get('summary') or '').strip()
	education = (data.get('education') or '').strip()
	experience = (data.get('experience') or '').strip()
	skills_raw = (data.get('skills') or '')
	job_desc = (data.get('job_description') or '').strip()

	# Normalize skills list
	skills = [s.strip().lower() for s in re.split('[,;\n]', skills_raw) if s.strip()]

	# Extract candidate sentences from experience
	exp_lines = [l.strip() for l in re.split('[\n\r]+', experience) if l.strip()]

	# Build job keywords: simple frequency-based selection excluding short/stop words
	tokens = re.findall(r"\b[a-zA-Z0-9+-]{3,}\b", job_desc.lower())
	STOP = set(['the','and','for','with','that','this','from','your','are','you','will','have','has','our','using','use','skills','responsibilities','requirements','role','team'])
	keywords = [t for t in tokens if t not in STOP]
	freq = {}
	for t in keywords:
		freq[t] = freq.get(t,0) + 1
	sorted_kw = sorted(freq.items(), key=lambda x: x[1], reverse=True)
	job_keywords = [k for k,_ in sorted_kw[:12]]

	# Match skills/keywords
	matched = [kw for kw in job_keywords if kw in ' '.join(skills) or kw in experience.lower() or kw in summary.lower()]
	matched = list(dict.fromkeys(matched))
	missing = [kw for kw in job_keywords if kw not in matched]
	score = int((len(matched) / max(1, len(job_keywords))) * 100)

	# Produce impact bullets by enhancing experience lines
	bullets = []
	for line in exp_lines:
		# If line contains a number, keep it; else prepend action verbs
		if re.search(r'\d', line):
			bullets.append(line)
		else:
			bullets.append('Led ' + line[0].lower() + line[1:] if line else line)
	if not bullets and summary:
		bullets = [summary]

	# Build resume HTML
	resume_html = []
	resume_html.append(f"<h2>{name}</h2>")
	contact = ' · '.join([p for p in [email, phone] if p])
	if contact:
		resume_html.append(f"<div class=\"muted\">{contact}</div>")
	if summary:
		resume_html.append(f"<h3>Summary</h3><p>{summary}</p>")
	if bullets:
		resume_html.append('<h3>Experience</h3><ul>')
		for b in bullets:
			resume_html.append(f"<li>{b}</li>")
		resume_html.append('</ul>')
	if education:
		resume_html.append(f"<h3>Education</h3><p>{education}</p>")
	if skills:
		resume_html.append('<h3>Skills</h3>')
		resume_html.append('<p>' + ', '.join([s.title() for s in skills]) + '</p>')

	resume_html = '\n'.join(resume_html)

	# Feedback text
	feedback = {
		'score': score,
		'matched': matched,
		'missing': missing,
		'summary': (
			'Good alignment — highlight these keywords in your bullets: ' + ', '.join(matched)
			if score >= 50 else
			'Low match — include or emphasize these keywords: ' + ', '.join(missing[:8])
		),
		'tips': [
			'Use numbers to quantify achievements (e.g., reduced X by 30%).',
			'Lead with impact: start bullets with action verbs and outcomes.',
			'Tailor your skills to match the job description keywords.',
		]
	}

	return jsonify({'resume_html': resume_html, 'feedback': feedback})


# Ensure tables are created (for Render + Gunicorn)
try:
	with app.app_context():
		db.create_all()
	print("[INIT] Database tables ensured.")
except Exception as e:
	print("[INIT ERROR] Failed to create tables:", e)


if __name__ == '__main__':
	port = int(os.environ.get('PORT', 5000))
	import sys

	# ensure stdout/stderr use utf-8 to avoid Windows encoding errors
	try:
		sys.stdout.reconfigure(encoding='utf-8')
		sys.stderr.reconfigure(encoding='utf-8')
	except Exception:
		pass

	print(f'[INIT] Starting Flask app on port {port}')
	app.run(host='0.0.0.0', port=port, debug=True)