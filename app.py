from flask import Flask, render_template, redirect, url_for, request, flash
from config import Config
from extensions import db, login_manager, socketio
from models import User, Project, Update, Comment, Collaboration
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)

# INIT EXTENSIONS
db.init_app(app)
login_manager.init_app(app)
socketio.init_app(app)

# ✅ FIX: redirect unauthorized users to login
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    # Use db.session.get() for SQLAlchemy 2.0 compatibility
    return db.session.get(User, int(user_id))


# ---------------- HOME / LANDING ---------------- #

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    # Get stats for landing page
    total_projects = Project.query.count()
    completed_projects = Project.query.filter_by(completed=True).count()
    total_devs = User.query.count()
    return render_template("home.html", 
                         total_projects=total_projects,
                         completed_projects=completed_projects,
                         total_devs=total_devs)


# ---------------- AUTH ---------------- #

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required", "error")
            return redirect(url_for("register"))

        existing_user = User.query.filter(
            (User.email == email) | (User.username == username)
        ).first()
        
        if existing_user:
            flash("Username or email already exists", "error")
            return redirect(url_for("register"))

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please log in.", "success")

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for("dashboard"))

        flash("Invalid email or password", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully", "success")
    return redirect(url_for("home"))


# ---------------- DASHBOARD ---------------- #

@app.route("/dashboard")
@login_required
def dashboard():
    my_projects = Project.query.filter_by(user_id=current_user.id)\
        .order_by(Project.created_at.desc()).all()
    
    # Get projects I'm collaborating on
    collaborations = Collaboration.query.filter_by(user_id=current_user.id).all()
    collab_project_ids = [c.project_id for c in collaborations]
    collab_projects = Project.query.filter(Project.id.in_(collab_project_ids)).all() if collab_project_ids else []
    
    return render_template("dashboard.html", 
                         projects=my_projects,
                         collab_projects=collab_projects)


# ---------------- PROJECT ---------------- #

@app.route("/create_project", methods=["GET", "POST"])
@login_required
def create_project():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        stage = request.form.get("stage", "")
        support_needed = request.form.get("support", "").strip()

        if not title or not description:
            flash("Title and description are required", "error")
            return redirect(url_for("create_project"))

        project = Project(
            title=title,
            description=description,
            stage=stage,
            support_needed=support_needed,
            user_id=current_user.id
        )

        db.session.add(project)
        db.session.commit()

        # Fixed socketio emit (removed broadcast parameter)
        socketio.emit("new_project", {
            "title": project.title,
            "user": current_user.username,
            "stage": project.stage
        })

        flash("Project created successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("create_project.html")


# ---------------- SINGLE PROJECT ---------------- #

@app.route("/project/<int:id>", methods=["GET", "POST"])
@login_required
def project(id):
    project = Project.query.get_or_404(id)
    is_owner = project.user_id == current_user.id
    
    # Check if current user is collaborating
    is_collaborating = Collaboration.query.filter_by(
        project_id=id, user_id=current_user.id
    ).first() is not None

    if request.method == "POST":
        if not is_owner and not is_collaborating:
            flash("Only the project owner or collaborators can add updates", "error")
            return redirect(url_for("project", id=id))
            
        content = request.form.get("update", "").strip()
        if content:
            update = Update(
                content=content,
                project_id=id,
                user_id=current_user.id
            )
            db.session.add(update)
            db.session.commit()
            flash("Update added!", "success")

    updates = Update.query.filter_by(project_id=id)\
        .order_by(Update.created_at.desc()).all()
    comments = Comment.query.filter_by(project_id=id)\
        .order_by(Comment.created_at.desc()).all()
    
    # Get collaborator info
    collabs = Collaboration.query.filter_by(project_id=id).all()
    collaborators = [User.query.get(c.user_id) for c in collabs]

    return render_template(
        "project.html",
        project=project,
        updates=updates,
        comments=comments,
        collaborators=collaborators,
        is_owner=is_owner,
        is_collaborating=is_collaborating
    )


# ---------------- FEED ---------------- #

@app.route("/feed", methods=["GET", "POST"])
@login_required
def feed():
    if request.method == "POST":
        content = request.form.get("comment", "").strip()
        project_id = request.form.get("project_id")
        
        if content and project_id:
            comment = Comment(
                content=content,
                project_id=int(project_id),
                user_id=current_user.id
            )
            db.session.add(comment)
            db.session.commit()
            flash("Comment added!", "success")

        return redirect(url_for("feed"))

    # Get all active projects with their owners
    projects = Project.query.filter_by(completed=False)\
        .order_by(Project.created_at.desc()).all()
    
    project_data = []
    for p in projects:
        owner = db.session.get(User, p.user_id)
        update_count = Update.query.filter_by(project_id=p.id).count()
        comment_count = Comment.query.filter_by(project_id=p.id).count()
        collab_count = Collaboration.query.filter_by(project_id=p.id).count()
        
        project_data.append({
            'project': p,
            'owner': owner,
            'update_count': update_count,
            'comment_count': comment_count,
            'collab_count': collab_count
        })

    return render_template("feed.html", projects=project_data)


# ---------------- COLLAB ---------------- #

@app.route("/collaborate/<int:project_id>")
@login_required
def collaborate(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Can't collaborate on own project
    if project.user_id == current_user.id:
        flash("You can't collaborate on your own project", "error")
        return redirect(url_for("feed"))

    existing = Collaboration.query.filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).first()

    if existing:
        flash("You're already collaborating on this project", "info")
    else:
        collab = Collaboration(
            project_id=project_id,
            user_id=current_user.id
        )
        db.session.add(collab)
        db.session.commit()
        flash("Collaboration request sent! 🎉", "success")

    return redirect(url_for("feed"))


# ---------------- COMPLETE ---------------- #

@app.route("/complete/<int:id>")
@login_required
def complete_project(id):
    project = Project.query.get_or_404(id)

    if project.user_id != current_user.id:
        flash("Not authorized", "error")
        return redirect(url_for("dashboard"))

    project.completed = True
    project.completed_at = datetime.utcnow()
    db.session.commit()
    
    flash("Congratulations! Project completed! 🎉", "success")

    return redirect(url_for("celebration"))


# ---------------- CELEBRATION ---------------- #

@app.route("/celebration")
@login_required
def celebration():
    projects = Project.query.filter_by(completed=True)\
        .order_by(Project.completed_at.desc()).all()
    
    celebrated = []
    for p in projects:
        owner = db.session.get(User, p.user_id)
        collabs = Collaboration.query.filter_by(project_id=p.id).all()
        collaborators = [db.session.get(User, c.user_id) for c in collabs]
        celebrated.append({
            'project': p,
            'owner': owner,
            'collaborators': collaborators
        })

    return render_template("celebration.html", projects=celebrated)


# ---------------- RUN ---------------- #

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    socketio.run(app, debug=True)