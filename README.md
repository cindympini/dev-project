DevHub
Build in Public Platform for Developers

DevHub is a web application where developers can share projects, collaborate with others, post updates, and celebrate completed work. Built with Flask and SQLite.

Features
User Authentication - Register, login, logout with secure password hashing

Project Management - Create projects with title, description, stage, and support needs

Collaboration - Other developers can join your projects as collaborators

Updates - Project owners and collaborators can post progress updates

Comments - Anyone can comment on any project

Feed - Browse all active projects with statistics

Celebration Page - Showcase completed projects

Tech Stack
Flask
SQLAlchemy
Flask-Login
Flask-SocketIO
SQLite
Werkzeug
Installation

bash
# Clone the repository
git clone https://github.com/cindympini/dev-project.git
cd dev-project

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py

Project Structure
text
dev-project/
├── app.py              # Main application with routes
├── models.py           # Database models
├── extensions.py       # Flask extensions setup
├── config.py           # Configuration settings
├── templates/          # HTML templates
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── create_project.html
│   ├── project.html
│   ├── feed.html
│   └── celebration.html
├── static/             # CSS and assets
│   └── style.css
├── test_app_final.py   # Test suite
└── requirements.txt    # Dependencies

Testing
Run the test suite to verify all critical features:

bash
python test_app_final.py
Tests cover:

User registration and login
Project creation
Updates (owner and collaborator)
Collaboration system
Project completion
Feed filtering

Database Models
User
Project
Update
Comment
Collaboration

Security
Password hashing (never stored in plain text)
SQL injection
XSS protection
Protected routes with @login_required
Owner/collaborator authorization checks
Unique constraints on emails and usernames

Live Demo
No live demo available. Run locally using installation steps above.

Author
Cindy Mpini

GitHub: @cindympini

Acknowledgments
Built as part of the Derivco Code Skills Challenge.
