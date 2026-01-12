from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask import send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

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
	name = db.Column(db.String(150))
	email = db.Column(db.String(150), unique=True, nullable=False)
	password_hash = db.Column(db.String(255), nullable=False)
	created_at = db.Column(db.DateTime, default=datetime.utcnow)

	def set_password(self, password: str):
		self.password_hash = generate_password_hash(password)

	def check_password(self, password: str) -> bool:
		return check_password_hash(self.password_hash, password)


def is_valid_email(email: str) -> bool:
	return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


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
def dashboard():
	user = None
	if session.get('user_id'):
		user = User.query.get(session['user_id'])
	return render_template('index.html', user=user)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
	if request.method == 'POST':
		name = request.form.get('name', '').strip()
		email = request.form.get('email', '').strip().lower()
		password = request.form.get('password', '')

		if not name or not email or not password:
			flash('Please fill all required fields', 'error')
			return redirect(url_for('signup'))

		if not is_valid_email(email):
			flash('Invalid email address', 'error')
			return redirect(url_for('signup'))

		if len(password) < 8:
			flash('Use at least 8 characters for the password', 'error')
			return redirect(url_for('signup'))

		existing = User.query.filter_by(email=email).first()
		if existing:
			flash('Email already registered. Please log in.', 'error')
			return redirect(url_for('login'))

		user = User(name=name, email=email)
		user.set_password(password)
		try:
			db.session.add(user)
			db.session.commit()
		except Exception:
			db.session.rollback()
			flash('An error occurred creating your account', 'error')
			return redirect(url_for('signup'))

		flash('Account created. Please log in.', 'success')
		return redirect(url_for('login'))

	return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'POST':
		email = request.form.get('email', '').strip().lower()
		password = request.form.get('password', '')

		user = User.query.filter_by(email=email).first()
		if not user or not user.check_password(password):
			flash('Invalid credentials', 'error')
			return redirect(url_for('login'))

		session['user_id'] = user.id
		session['user_name'] = user.name
		flash('Logged in successfully', 'success')
		return redirect(url_for('dashboard'))

	return render_template('login.html')


@app.route('/logout')
def logout():
	session.clear()
	flash('Logged out', 'info')
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


@app.route('/chat', methods=['POST'])
def chat():
	"""Improved resume chatbot with intelligent rewriting, keyword matching, and context-aware responses."""
	data = request.get_json(silent=True) or {}
	message = (data.get('message') or '').strip()
	context = (data.get('context') or '').strip().lower()
	resume_text = (data.get('resume') or '')
	if not message:
		return jsonify({'reply': 'Tell me how I can help: improve bullets, suggest keywords, or rewrite text.'}), 400

	# Optional LLM integration: if client requests `use_llm: true` or environment forces LLM,
	# and an `OPENAI_API_KEY` is present, forward the message to the provider and return.
	use_llm = bool(data.get('use_llm')) or os.environ.get('USE_LLM', '').lower() in ('1','true','yes')
	OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

	def call_openai_chat(prompt: str, system: str | None = None, model: str | None = None) -> str | None:
		"""Call OpenAI-compatible chat completions API (best-effort). Returns assistant text or None."""
		if requests is None:
			print('Requests library not available; cannot call external LLM.')
			return None
		if not OPENAI_API_KEY:
			print('OPENAI_API_KEY not set; skipping LLM call')
			return None
		model = model or os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
		url = os.environ.get('OPENAI_API_URL', 'https://api.openai.com/v1/chat/completions')
		headers = {
			'Authorization': f'Bearer {OPENAI_API_KEY}',
			'Content-Type': 'application/json'
		}
		messages = []
		if system:
			messages.append({'role': 'system', 'content': system})
		messages.append({'role': 'user', 'content': prompt})
		payload = {
			'model': model,
			'messages': messages,
			'temperature': float(os.environ.get('OPENAI_TEMPERATURE', 0.2)),
			'max_tokens': int(os.environ.get('OPENAI_MAX_TOKENS', 512))
		}
		try:
			r = requests.post(url, headers=headers, json=payload, timeout=15)
			if r.status_code != 200:
				print(f'LLM request failed: {r.status_code} {r.text}')
				return None
			data = r.json()
			# Best-effort extraction for common OpenAI response shapes
			choices = data.get('choices') or []
			if choices:
				text = choices[0].get('message', {}).get('content') or choices[0].get('text')
				return text
			# Fallback
			return None
		except Exception as e:
			print(f'Exception calling LLM: {e}')
			return None

	if use_llm and OPENAI_API_KEY:
		# Ask the LLM to behave like the resume assistant and include the resume context
		system_prompt = (
			"You are a concise, helpful assistant specialized in improving resumes: rewriting bullets, extracting keywords,"
			" suggesting metrics, and matching resumes to job descriptions. Keep responses actionable and brief."
		)
		# include resume_text to give context if present
		prompt = message
		if resume_text:
			prompt = f"Resume Context:\n{resume_text}\n\nUser Request:\n{message}"
		llm_reply = call_openai_chat(prompt, system=system_prompt)
		if llm_reply:
			return jsonify({'reply': llm_reply, 'source': 'llm'})
		# If LLM failed, fall through to rule-based assistant and include a notice
		print('LLM call failed or returned no text; using local rule-based assistant')

	msg = message.lower()
	
	def smart_rewrite(text):
		"""Enhance bullets with action verbs, metrics, and stronger phrasing."""
		lines = [l.strip().lstrip('-*•· ').strip() for l in text.splitlines() if l.strip()]
		if not lines:
			return ''
		
		# Action verbs grouped by intensity
		verbs_high = ['Spearheaded','Engineered','Architected','Orchestrated','Transformed']
		verbs_med = ['Implemented','Optimized','Developed','Designed','Led']
		verbs_low = ['Improved','Enhanced','Managed','Created','Built']
		
		def get_verb(idx):
			choice = idx % 3
			if choice == 0: return verbs_high[idx % len(verbs_high)]
			elif choice == 1: return verbs_med[idx % len(verbs_med)]
			else: return verbs_low[idx % len(verbs_low)]
		
		def add_metrics(bullet):
			"""If bullet lacks quantifiable metrics, suggest adding them."""
			has_num = any(c.isdigit() for c in bullet)
			if not has_num and len(bullet) > 10:
				return bullet + ' (consider adding: %, #, or $)'
			return bullet
		
		out_lines = []
		for i, ln in enumerate(lines):
			if not ln:
				continue
			words = ln.split()
			first_word = words[0].lower() if words else ''
			
			# Check if starts with a weak phrase
			if first_word in ('the','a','an','worked','made','did','helped','was','were','used','got'):
				verb = get_verb(i)
				rest = ' '.join(words)
				if first_word in ('the','a','an'):
					out = f"{verb} {rest[len(first_word):].lstrip()}"
				else:
					out = f"{verb} {' '.join(words[1:])}"
			else:
				out = ln[0].upper() + ln[1:] if ln else ''
			
			# Add metric suggestion if missing
			out = add_metrics(out)
			out_lines.append('• ' + out)
		
		return '\n'.join(out_lines)
	
	def extract_keywords_from_text(text):
		"""Extract meaningful keywords from job description or resume."""
		import re
		# Look for tech terms, methodologies, frameworks
		tech_keywords = [
			'python', 'javascript', 'java', 'react', 'angular', 'vue', 'nodejs', 'django', 'flask',
			'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git', 'agile', 'scrum',
			'sql', 'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch', 'graphql', 'rest',
			'machine learning', 'deep learning', 'nlp', 'tensorflow', 'pytorch', 'keras',
			'ci/cd', 'devops', 'microservices', 'api', 'saas', 'cloud'
		]
		text_lower = text.lower()
		found = [kw for kw in tech_keywords if kw in text_lower]
		return found[:5] if found else []
	
	# IMPROVE / REWRITE
	if any(k in msg for k in ('improve', 'rewrite', 'enhance', 'make better')):
		if ':' in message:
			payload = message.split(':', 1)[1].strip()
		else:
			payload = message.replace('improve', '').replace('rewrite', '').replace('enhance', '').replace('make better', '').strip()
		
		if payload and len(payload) > 5:
			rewritten = smart_rewrite(payload)
			if rewritten:
				suggestions = "Tips: Use action verbs, include metrics (%, $, #), and quantify impact." if context == 'builder' else "Your improved version is ready to use."
				reply = f"✓ Improved version:\n{rewritten}\n\n💡 {suggestions}"
			else:
				reply = "I can enhance your bullet points with stronger action verbs and clearer impact. Send me 1-3 bullets to improve."
		else:
			reply = "Send me a bullet point or achievement and I'll rewrite it to be more impactful with stronger action verbs and metrics."
	
	# KEYWORDS / JOB MATCHING
	elif any(k in msg for k in ('keyword', 'match', 'job', 'missing', 'skills to add')):
		if ':' in message:
			job_desc = message.split(':', 1)[1].strip()
		else:
			job_desc = resume_text
		
		suggested = extract_keywords_from_text(job_desc)
		resume_kws = extract_keywords_from_text(resume_text)
		missing = [kw for kw in suggested if kw not in [r.lower() for r in resume_kws]]
		
		if suggested:
			reply_msg = f"📌 Key skills found in job description: {', '.join(suggested[:4])}\n"
			if missing:
				reply_msg += f"⚠️ Missing from your resume: {', '.join(missing[:3])}\n"
				reply_msg += "💡 Try adding these to your skills or experience bullets."
			else:
				reply_msg += "✓ Great! You have most of the key skills."
			reply = reply_msg
		else:
			reply = "Paste a job description or tell me what role you're targeting, and I'll suggest key skills to highlight."
	
	# HELP / GENERAL
	elif any(k in msg for k in ('help', 'what can you do', 'capabilities', 'commands')):
		reply = (
			"🤖 I can help you:\n\n"
			"✏️ Improve bullets: 'Improve: <your text>'\n"
			"🔍 Match job keywords: 'Keywords: <job description>' or 'Match: <role>'\n"
			"🎯 Enhance summary: 'Rewrite: <your summary>'\n"
			"📊 Add metrics: 'Add impact to: <text>'\n\n"
			"Just paste your text after the command and I'll enhance it!"
		)
	
	# FEEDBACK / SCORE
	elif any(k in msg for k in ('score', 'feedback', 'rate', 'evaluate')):
		if resume_text and len(resume_text) > 20:
			has_verbs = any(v in resume_text.lower() for v in ['led', 'managed', 'designed', 'improved'])
			has_metrics = any(c.isdigit() for c in resume_text)
			score = 60
			if has_verbs: score += 15
			if has_metrics: score += 15
			feedback = []
			if not has_verbs: feedback.append('- Use stronger action verbs (Led, Designed, Implemented)')
			if not has_metrics: feedback.append('- Add quantifiable metrics (%, $, #)')
			if len(resume_text) < 100: feedback.append('- Add more detail to achievements')
			reply = f"📈 Resume Strength: {score}%\n\nSuggestions:\n" + '\n'.join(feedback[:3]) if feedback else f"✓ Looking good! Score: {score}%"
		else:
			reply = "Send me your resume text or a bullet to evaluate, and I'll give you feedback."
	
	# DEFAULT
	else:
		reply = (
			"💬 I can help improve your resume. Try:\n\n"
			"'Improve: [your text]' → Better phrasing & action verbs\n"
			"'Keywords: [job description]' → Skills to add\n"
			"'Help' → See all commands"
		)
	
	return jsonify({'reply': reply})


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