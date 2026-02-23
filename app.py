from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask import send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta
import logging
import google.generativeai as genai

try:
	import PyPDF2
except Exception:
	PyPDF2 = None

try:
	from fpdf import FPDF
	print("✓ FPDF library loaded successfully")
except ImportError as e:
	FPDF = None
	print(f"✗ FPDF import failed: {e}")

import os
from datetime import datetime
import re
try:
	import requests
except Exception:
	requests = None

app = Flask(__name__)
# Use an environment variable for production secret; fallback for local dev
app.secret_key = os.environ.get('SECRET_KEY', 'dev_change_me_to_secure_random')

# Session configuration for security
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Enable CSRF protection
csrf = CSRFProtect(app)

# Setup logging for authentication
logging.basicConfig(level=logging.INFO)
auth_logger = logging.getLogger('auth')

# Configure Gemini API
GEMINI_API_KEY = 'AIzaSyA2kTypsJMx4o1quNX2aQxWex4WnGs1mZk'
genai.configure(api_key=GEMINI_API_KEY)

# Database (SQLite for local/dev). For production, replace with PostgreSQL or other DB.
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'site.db')
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
		self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

	def check_password(self, password: str) -> bool:
		"""Verify the provided password against the hash"""
		return check_password_hash(self.password_hash, password)
	
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


def generate_resume_pdf(name: str, email: str, phone: str, summary: str, education: str, experience: str, achievements: str, skills: str, declaration: str) -> bytes:
	"""Generate a professional resume PDF using FPDF - Simple and clean"""
	if FPDF is None:
		print("ERROR: FPDF library not loaded!")
		return None
	
	try:
		# Sanitize all inputs to ensure they're safe for PDF
		name = str(name or "").strip()
		email = str(email or "").strip()
		phone = str(phone or "").strip()
		summary = str(summary or "").strip()
		education = str(education or "").strip()
		experience = str(experience or "").strip()
		achievements = str(achievements or "").strip()
		skills = str(skills or "").strip()
		declaration = str(declaration or "").strip()
		
		if not name:
			print("ERROR: Name is required for PDF generation")
			return None
		
		pdf = FPDF(format='A4')
		pdf.add_page()
		pdf.set_auto_page_break(auto=True, margin=15)
		
		# Title - Name
		pdf.set_font("Arial", "B", 18)
		pdf.set_text_color(40, 50, 100)
		pdf.cell(0, 10, name, align="C", new_x="LMARGIN", new_y="NEXT")
		
		# Contact information
		pdf.set_font("Arial", "", 10)
		pdf.set_text_color(100, 100, 100)
		contact_list = []
		if email:
			contact_list.append(email)
		if phone:
			contact_list.append(phone)
		
		if contact_list:
			contact_text = " | ".join(contact_list)
			pdf.cell(0, 5, contact_text, align="C", new_x="LMARGIN", new_y="NEXT")
		
		# Separator line
		pdf.set_draw_color(150, 150, 200)
		pdf.line(15, pdf.get_y(), 195, pdf.get_y())
		pdf.ln(5)
		
		# Professional Summary Section
		if summary:
			pdf.set_font("Arial", "B", 11)
			pdf.set_text_color(40, 50, 100)
			pdf.cell(0, 6, "PROFESSIONAL SUMMARY", new_x="LMARGIN", new_y="NEXT")
			# Add line below heading
			pdf.set_draw_color(150, 150, 200)
			pdf.line(15, pdf.get_y(), 195, pdf.get_y())
			pdf.ln(3)
			pdf.set_font("Arial", "", 10)
			pdf.set_text_color(0, 0, 0)
			try:
				pdf.multi_cell(0, 5, summary)
			except Exception as e:
				print(f"Warning: Error in summary: {e}")
				pdf.multi_cell(0, 5, "[Summary could not be displayed]")
			pdf.ln(2)
		
		# Experience Section
		if experience:
			pdf.set_font("Arial", "B", 11)
			pdf.set_text_color(40, 50, 100)
			pdf.cell(0, 6, "EXPERIENCE", new_x="LMARGIN", new_y="NEXT")
			# Add line below heading
			pdf.set_draw_color(150, 150, 200)
			pdf.line(15, pdf.get_y(), 195, pdf.get_y())
			pdf.ln(3)
			pdf.set_font("Arial", "", 10)
			pdf.set_text_color(0, 0, 0)
			try:
				exp_lines = experience.split('\n')
				for exp_line in exp_lines:
					clean_line = exp_line.strip()
					if clean_line:
						pdf.multi_cell(0, 5, clean_line)
			except Exception as e:
				print(f"Warning: Error in experience: {e}")
			pdf.ln(2)
		
		# Education Section
		if education:
			pdf.set_font("Arial", "B", 11)
			pdf.set_text_color(40, 50, 100)
			pdf.cell(0, 6, "EDUCATION", new_x="LMARGIN", new_y="NEXT")
			# Add line below heading
			pdf.set_draw_color(150, 150, 200)
			pdf.line(15, pdf.get_y(), 195, pdf.get_y())
			pdf.ln(3)
			pdf.set_font("Arial", "", 10)
			pdf.set_text_color(0, 0, 0)
			try:
				edu_lines = education.split('\n')
				for edu_line in edu_lines:
					clean_line = edu_line.strip()
					if clean_line:
						pdf.multi_cell(0, 5, clean_line)
			except Exception as e:
				print(f"Warning: Error in education: {e}")
			pdf.ln(2)
		
		# Achievements Section
		if achievements:
			pdf.set_font("Arial", "B", 11)
			pdf.set_text_color(40, 50, 100)
			pdf.cell(0, 6, "ACHIEVEMENTS", new_x="LMARGIN", new_y="NEXT")
			# Add line below heading
			pdf.set_draw_color(150, 150, 200)
			pdf.line(15, pdf.get_y(), 195, pdf.get_y())
			pdf.ln(3)
			pdf.set_font("Arial", "", 10)
			pdf.set_text_color(0, 0, 0)
			try:
				ach_lines = achievements.split('\n')
				for ach_line in ach_lines:
					clean_ach = ach_line.strip()
					if clean_ach:
						pdf.multi_cell(0, 5, "- " + clean_ach)
			except Exception as e:
				print(f"Warning: Error in achievements: {e}")
			pdf.ln(2)
		
		# Skills Section
		if skills:
			pdf.set_font("Arial", "B", 11)
			pdf.set_text_color(40, 50, 100)
			pdf.cell(0, 6, "SKILLS", new_x="LMARGIN", new_y="NEXT")
			# Add line below heading
			pdf.set_draw_color(150, 150, 200)
			pdf.line(15, pdf.get_y(), 195, pdf.get_y())
			pdf.ln(3)
			pdf.set_font("Arial", "", 10)
			pdf.set_text_color(0, 0, 0)
			try:
				skills_text = skills.replace('\n', ', ')
				pdf.multi_cell(0, 5, skills_text)
			except Exception as e:
				print(f"Warning: Error in skills: {e}")
			pdf.ln(2)
		
		# Declaration Section
		if declaration:
			pdf.set_font("Arial", "B", 11)
			pdf.set_text_color(40, 50, 100)
			pdf.cell(0, 6, "DECLARATION", new_x="LMARGIN", new_y="NEXT")
			# Add line below heading
			pdf.set_draw_color(150, 150, 200)
			pdf.line(15, pdf.get_y(), 195, pdf.get_y())
			pdf.ln(3)
			pdf.set_font("Arial", "", 10)
			pdf.set_text_color(0, 0, 0)
			try:
				pdf.multi_cell(0, 5, declaration)
			except Exception as e:
				print(f"Warning: Error in declaration: {e}")
		
		pdf_bytes = pdf.output()
		print(f"✓ PDF generated successfully ({len(pdf_bytes)} bytes)")
		return pdf_bytes
		
	except Exception as e:
		print(f"ERROR in PDF generation: {str(e)}")
		import traceback
		traceback.print_exc()
		return None


# Database initialization is handled by the run scripts or the Flask CLI; avoid
# creating tables at import-time in case of test/import scenarios.


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
	if request.method == 'POST':
		name = request.form.get('name', '').strip()
		email = request.form.get('email', '').strip().lower()
		password = request.form.get('password', '')
		confirm_password = request.form.get('confirm_password', '')

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

		existing = User.query.filter_by(email=email).first()
		if existing:
			flash('Email already registered. Please log in.', 'error')
			return redirect(url_for('login'))

		# Create new user
		user = User(name=name, email=email, is_active=True)
		user.set_password(password)
		try:
			db.session.add(user)
			db.session.commit()
			auth_logger.info(f"New account created: {email}")
			flash('Account created successfully. Please log in.', 'success')
			return redirect(url_for('login'))
		except Exception as e:
			db.session.rollback()
			auth_logger.error(f"Signup error for {email}: {str(e)}")
			flash('An error occurred creating your account', 'error')
			return redirect(url_for('signup'))

	return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'POST':
		email = request.form.get('email', '').strip().lower()
		password = request.form.get('password', '')

		if not email or not password:
			flash('Please provide both email and password', 'error')
			return redirect(url_for('login'))

		user = User.query.filter_by(email=email).first()
		
		# Check if account is locked
		if user and user.is_locked():
			flash('Account locked due to too many failed attempts. Try again in 15 minutes.', 'error')
			auth_logger.warning(f"Login attempt on locked account: {email}")
			return redirect(url_for('login'))

		# Check credentials
		if not user or not user.check_password(password):
			if user:
				user.record_failed_login()
				auth_logger.warning(f"Failed login attempt: {email} (Attempt {user.failed_attempts})")
			else:
				auth_logger.warning(f"Login attempt with non-existent email: {email}")
			
			# Log the failed attempt
			if user:
				login_history = LoginHistory(
					user_id=user.id,
					ip_address=get_client_ip(),
					user_agent=request.headers.get('User-Agent', '')[:255],
					success=False
				)
				db.session.add(login_history)
				db.session.commit()
			
			flash('Invalid email or password', 'error')
			return redirect(url_for('login'))

		# Successful login
		if not user.is_active:
			flash('Your account has been deactivated', 'error')
			auth_logger.warning(f"Login attempt on inactive account: {email}")
			return redirect(url_for('login'))

		user.reset_failed_attempts()
		
		# Log successful login
		login_history = LoginHistory(
			user_id=user.id,
			ip_address=get_client_ip(),
			user_agent=request.headers.get('User-Agent', '')[:255],
			success=True
		)
		db.session.add(login_history)
		db.session.commit()

		# Set session
		session.permanent = True
		session['user_id'] = user.id
		session['user_name'] = user.name
		session['user_email'] = user.email
		
		auth_logger.info(f"Successful login: {email} from {get_client_ip()}")
		flash(f'Welcome back, {user.name}!', 'success')
		return redirect(url_for('dashboard'))

	return render_template('login.html')


@app.route('/logout')
def logout():
	user_email = session.get('user_email', 'unknown')
	session.clear()
	auth_logger.info(f"User logged out: {user_email}")
	flash('Logged out successfully', 'info')
	return redirect(url_for('index'))


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

			# Generate PDF resume
			if FPDF is None:
				message = 'PDF generation library not available.'
				print(f"ERROR: FPDF is None!")
				return render_template('builder.html', message=message)
			
			pdf_content = generate_resume_pdf(name, email, phone, summary, education, experience, achievements, skills, declaration)
			
			if pdf_content is None:
				message = 'Failed to generate PDF. Please check your input and try again.'
				print(f"ERROR: PDF content is None after generation attempt")
				return render_template('builder.html', message=message)
			
			# Save PDF file
			safe_name = secure_filename(name) or 'resume'
			timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
			filename = f"{safe_name}_{timestamp}.pdf"
			save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
			
			with open(save_path, 'wb') as fh:
				fh.write(pdf_content)
			
			message = f"✓ Professional resume created successfully for {name}!"
			download = filename
			print(f"✓ Resume saved: {filename}")
			
		except Exception as e:
			message = f'Error: {str(e)}'
			print(f"ERROR in builder route: {str(e)}")
			import traceback
			traceback.print_exc()

	return render_template('builder.html', message=message, download=download)


@app.route('/chat', methods=['POST', 'GET', 'OPTIONS'])
@csrf.exempt  # Exempt chat from CSRF since it's called from JavaScript
def chat():
	"""Real-time resume assistant with intelligent local responses"""
	# Handle CORS preflight
	if request.method == 'OPTIONS':
		response = jsonify({'status': 'ok'})
		response.headers.add('Access-Control-Allow-Origin', '*')
		response.headers.add('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
		response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
		return response, 200
	
	if request.method == 'GET':
		return jsonify({'status': 'ok', 'message': 'Chat endpoint is working'}), 200
	
	try:
		print(f"\n[CHAT] Request received")
		
		data = request.get_json(silent=True) or {}
		message = (data.get('message') or '').strip()
		
		if not message:
			return jsonify({'reply': 'How can I help? Ask anything about your resume!'}), 200
		
		msg_lower = message.lower()
		print(f"[CHAT] Message: '{message}'")
		
		# Local response system - No API timeouts
		if any(word in msg_lower for word in ['improve', 'better', 'enhance', 'bullet']):
			reply = "Use action verbs (Led, Developed, Increased), add numbers/metrics, show impact, and be specific. Example: 'Led redesign of website, improving load speed by 40%' vs 'Worked on website'."
		
		elif any(word in msg_lower for word in ['keyword', 'ats', 'optimize']):
			reply = "Match job description keywords, use clear section headings (Experience, Skills, Education), keep plain text (no graphics), match job titles, create a dedicated skills list."
		
		elif any(word in msg_lower for word in ['summary', 'profile', 'objective', 'intro']):
			reply = "Write: 'Results-driven [Role] with [X years] in [Industry]. Proven expertise in [Skills]. Skilled in [Technical]. Seeking [Position].' Make it specific to your target role."
		
		elif any(word in msg_lower for word in ['skill', 'add', 'competency']):
			reply = "List: Technical skills (languages, tools), Soft skills (Leadership, Communication), Industry expertise, Management/Project skills. Prioritize skills from the job you're applying for."
		
		elif any(word in msg_lower for word in ['metric', 'number', 'impact', 'result', 'achieve']):
			reply = "Add metrics: Revenue ($2M), Performance (35% improvement), Time (2-month reduction), Scale (team of 12), Quality (99.9% uptime), Growth (150% increase)."
		
		elif any(word in msg_lower for word in ['format', 'structure', 'layout']):
			reply = "Best format: Name + contact info at top, 2-3 line summary, experience (recent first), skills section, education. 1-2 pages, clear headings, bullets, standard fonts, save as PDF."
		
		elif any(word in msg_lower for word in ['experience', 'job', 'work', 'position']):
			reply = "Format: [Action Verb] [Task] [Result]. Example: 'Led team of 8 to deliver CRM 2 weeks early, saving $500K.' Use 4-6 bullets per job with metrics."
		
		elif any(word in msg_lower for word in ['education', 'degree', 'certification', 'course']):
			reply = "Include: Degree, University, Date, Relevant coursework, Honors (GPA > 3.5), Certifications. Format: Bachelor Science Computer Science | MIT | May 2020."
		
		elif any(word in msg_lower for word in ['project', 'portfolio', 'github']):
			reply = "List: Project name, Tech stack, Brief 1-2 line description, Impact/users. Example: Task App (React, Node, MongoDB) - Real-time collaboration tool, 500+ users."
		
		else:
			reply = "Resume Coach here! Ask me about: bullets, keywords/ATS, summary, skills, metrics, format, experience, education, or projects. What would you like help with?"
		
		print(f"[CHAT] Response generated: {len(reply)} chars")
		return jsonify({'reply': reply}), 200
	
	except Exception as e:
		print(f"[CHAT ERROR] {type(e).__name__}: {str(e)}")
		import traceback
		traceback.print_exc()
		return jsonify({'reply': 'Error processing request. Please try again.'}), 500


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
				# extract text
				text = ''
				_, ext = os.path.splitext(filename.lower())
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
									pages.append(p.extract_text() or '')
								except Exception:
									pages.append('')
							text = '\n'.join(pages)
					else:
						# For .doc/.docx or if PyPDF2 not installed, fall back to empty text
						text = ''
				except Exception:
					text = ''

				# Role keyword matching
				ROLE_KEYWORDS = {
					'Data Scientist': ['python','machine learning','statistics','pandas','numpy','model','data','analysis','deep learning','regression'],
					'Frontend Developer': ['javascript','react','css','html','frontend','typescript','vue','angular','ui','ux'],
					'Backend Developer': ['python','java','node','api','django','flask','sql','database','backend','rest'],
					'DevOps Engineer': ['docker','kubernetes','ci/cd','aws','terraform','ansible','monitoring','sre','jenkins'],
					'Product Manager': ['roadmap','stakeholder','product','metrics','agile','scrum','user research','roadmap']
				}

				keywords = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS['Data Scientist'])
				text_l = (text or '').lower()
				matched = [kw for kw in keywords if kw in text_l]
				missing = [kw for kw in keywords if kw not in text_l]
				score = int((len(matched) / max(1, len(keywords))) * 100)

				if score >= 60:
					suggestion = 'Resume looks suitable for this role. Consider adding more quantifiable achievements if possible.'
				else:
					suggestion = 'Tailor your resume to the role: add or emphasize skills: ' + ', '.join(missing[:6]) + '. Also highlight relevant projects and measurable outcomes.'

				result = {
					'role': role,
					'score': score,
					'matched': matched,
					'missing': missing,
					'suggestion': suggestion
				}
		else:
			result = 'No file selected.'
	return render_template('analyzer_v2.html', result=result)


@app.route('/ai_resume', methods=['POST'])
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


if __name__ == '__main__':
	port = int(os.environ.get('PORT', 5000))
	# For local debugging enable debug mode temporarily to get stack traces in browser.
	# Remember to disable debug in production.
	with app.app_context():
		db.create_all()
	print('Database initialized.')
	print(f'Starting Flask app on http://127.0.0.1:{port}')
	app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)