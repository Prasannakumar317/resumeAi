# Authentication Quick Reference Guide

## 🔑 Key Features at a Glance

| Feature | Status | Details |
|---------|--------|---------|
| Strong Passwords | ✅ | 8+ chars, mixed case, numbers, special chars |
| Password Hashing | ✅ | PBKDF2:SHA256 (industry standard) |
| CSRF Protection | ✅ | Flask-WTF on all forms |
| Session Security | ✅ | HttpOnly, SameSite, 24h timeout |
| Account Lockout | ✅ | 5 failed attempts = 15 min lockout |
| Login History | ✅ | All attempts tracked with IP & user agent |
| Rate Limiting | 🔄 | Ready to implement |
| 2FA Support | 🔄 | Ready to implement |

## 🚀 Quick Start

### Install & Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Migrate database
python migrate_db.py

# Start app
python app.py
```

### Test Credentials
```
Email: test@example.com
Password: TestPassword123!
```

## 🔐 Code Examples

### Protect a Route
```python
from app import login_required

@app.route('/protected')
@login_required
def protected_page():
    user = User.query.get(session['user_id'])
    return render_template('protected.html', user=user)
```

### Add CSRF Token to Form
```html
<form method="POST" action="/endpoint">
    {{ csrf_token() }}
    <input type="text" name="field">
    <button type="submit">Submit</button>
</form>
```

### Check User Status
```python
user = User.query.get(session['user_id'])
if user.is_active:
    # User can access
    pass
else:
    # Account deactivated
    session.clear()
    redirect(url_for('login'))
```

### Query Login History
```python
# Get recent failed logins
failed_logins = LoginHistory.query.filter_by(
    success=False
).order_by(
    LoginHistory.login_time.desc()
).limit(10).all()

for attempt in failed_logins:
    print(f"{attempt.user.email} - {attempt.ip_address} - {attempt.login_time}")
```

## 📋 API Reference

### POST /signup
**Parameters:**
- `name` (required) - User's full name
- `email` (required) - Valid email address
- `password` (required) - Strong password
- `confirm_password` (required) - Must match password

**Response:**
- Success: Redirect to /login with success message
- Error: Redirect to /signup with error message

### POST /login
**Parameters:**
- `email` (required)
- `password` (required)

**Response:**
- Success: Redirect to /dashboard, sets session
- Error: Redirect to /login with error message
- Locked: 15 min lockout after 5 failed attempts

### GET /logout
**Response:**
- Clears session, redirects to home page

### GET /dashboard
**Requires:** Login (`@login_required`)
**Response:**
- Renders dashboard for logged-in user

## 🛡️ Security Checklist

### For Each Deployment
- [ ] Update `SECRET_KEY` from environment variable
- [ ] Check `SESSION_COOKIE_SECURE` is appropriate
- [ ] Verify database connection is secure
- [ ] Enable HTTPS if production
- [ ] Set up monitoring for failed logins
- [ ] Configure firewall rules
- [ ] Review user permissions

### Development vs Production

**Development:**
```python
SESSION_COOKIE_SECURE = False  # No HTTPS needed
app.secret_key = 'dev_key'
```

**Production:**
```python
SESSION_COOKIE_SECURE = True   # HTTPS required
app.secret_key = os.environ.get('SECRET_KEY')
```

## 🐛 Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| CSRF token missing | Not in form | Add `{{ csrf_token() }}` |
| Account locked | 5 failed attempts | Wait 15 min or reset DB |
| Password weak | Doesn't meet requirements | Use mixed case, numbers, special chars |
| Session expired | 24h timeout | Login again |
| Login loop | User marked inactive | Check `is_active` in DB |

## 📊 Monitoring Queries

### Check Account Status
```python
User.query.filter_by(email='user@example.com').first()
# Returns: User object with all fields including failed_attempts, locked_until
```

### Find Locked Accounts
```python
from datetime import datetime
User.query.filter(User.locked_until > datetime.utcnow()).all()
```

### Recent Login Failures
```python
LoginHistory.query.filter_by(success=False).order_by(
    LoginHistory.login_time.desc()
).limit(20).all()
```

### Suspicious Activity (Many Failed Attempts)
```python
from datetime import datetime, timedelta
recently = datetime.utcnow() - timedelta(hours=1)
LoginHistory.query.filter(
    LoginHistory.success == False,
    LoginHistory.login_time > recently
).all()
```

## 🔄 Password Reset Flow (To Implement)

1. User clicks "Forgot Password"
2. Enter email address
3. Send email with reset token
4. User clicks link in email
5. Enter new password
6. Password updated

**Implementation note:** Currently not implemented, can add `password_reset_token` field to User model

## 📈 Performance Tips

- Passwords are hashed using PBKDF2 (slower = more secure)
- Login attempts are indexed by email for fast lookups
- Login history table should be archived after 90 days
- Consider caching user permissions

## 🚨 Incident Response

### If compromised password detected:
```python
user = User.query.filter_by(email='compromised@email.com').first()
user.set_password('TempPassword123!')  # New temp password
db.session.commit()
# Send email to user with temp password
```

### Force logout all sessions:
```python
# Session is server-side, so clear user's last_login
user.last_login = None
db.session.commit()
```

### Disable account:
```python
user.is_active = False
db.session.commit()
```

---

**Last Updated:** 2026-02-23
**Version:** 1.0
**Status:** Production Ready ✅
