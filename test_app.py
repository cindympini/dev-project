# test_app.py
import unittest
from flask import Flask
from config import Config
from extensions import db, login_manager, socketio
from models import User, Project, Update, Comment, Collaboration
from werkzeug.security import generate_password_hash

class TestDevCollab(unittest.TestCase):
    """Test suite for DevCollab application"""
    
    def setUp(self):
        """Set up test database and client"""
        # Create app for testing
        self.app = Flask(__name__)
        self.app.config.from_object(Config)
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['SERVER_NAME'] = 'localhost.localdomain'
        self.app.config['LOGIN_DISABLED'] = False
        
        # Initialize extensions
        db.init_app(self.app)
        login_manager.init_app(self.app)
        socketio.init_app(self.app)
        
        # Set login view
        login_manager.login_view = "login"
        
        # Import routes after app creation to avoid circular imports
        from app import register_routes
        register_routes(self.app)
        
        # Create test client
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            self._create_test_data()
    
    def tearDown(self):
        """Clean up after tests"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def _create_test_data(self):
        """Create test users and projects"""
        # Create test users with proper password hashing
        self.user1 = User(
            username="testuser1",
            email="test1@example.com",
            password=generate_password_hash("password123")
        )
        self.user2 = User(
            username="testuser2", 
            email="test2@example.com",
            password=generate_password_hash("password456")
        )
        db.session.add_all([self.user1, self.user2])
        db.session.commit()
        
        # Store IDs for later use (avoid detached instance issues)
        self.user1_id = self.user1.id
        self.user2_id = self.user2.id
        
        # Create test project
        self.project = Project(
            title="Test Project",
            description="Test Description",
            stage="development",
            support_needed="Testing help",
            user_id=self.user1_id
        )
        db.session.add(self.project)
        db.session.commit()
        self.project_id = self.project.id
        
        # Create test update
        self.update = Update(
            content="Test update content",
            project_id=self.project_id,
            user_id=self.user1_id
        )
        db.session.add(self.update)
        db.session.commit()
        
        # Create test comment
        self.comment = Comment(
            content="Test comment",
            project_id=self.project_id,
            user_id=self.user2_id
        )
        db.session.add(self.comment)
        db.session.commit()
        
        # Create test collaboration
        self.collab = Collaboration(
            project_id=self.project_id,
            user_id=self.user2_id
        )
        db.session.add(self.collab)
        db.session.commit()
    
    # Helper methods
    def _login_user1(self):
        """Helper to login as testuser1"""
        return self.client.post('/login', data={
            'email': 'test1@example.com',
            'password': 'password123'
        }, follow_redirects=True)
    
    def _login_user2(self):
        """Helper to login as testuser2"""
        return self.client.post('/login', data={
            'email': 'test2@example.com',
            'password': 'password456'
        }, follow_redirects=True)
    
    # ---------- AUTHENTICATION TESTS ----------
    
    def test_user_registration(self):
        """Test user registration functionality"""
        with self.app.app_context():
            response = self.client.post('/register', data={
                'username': 'newuser',
                'email': 'new@example.com',
                'password': 'password123'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Account created', response.data)
            
            # Verify user was created
            user = User.query.filter_by(email='new@example.com').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.username, 'newuser')
    
    def test_user_login(self):
        """Test user login functionality"""
        with self.app.app_context():
            response = self.client.post('/login', data={
                'email': 'test1@example.com',
                'password': 'password123'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            # Should redirect to dashboard (check for dashboard content or redirect)
            self.assertIn(b'Dashboard', response.data)
    
    def test_invalid_login(self):
        """Test login with invalid credentials"""
        with self.app.app_context():
            response = self.client.post('/login', data={
                'email': 'test1@example.com',
                'password': 'wrongpassword'
            }, follow_redirects=True)
            
            self.assertIn(b'Invalid email or password', response.data)
    
    def test_protected_route_requires_login(self):
        """Test that protected routes redirect to login"""
        response = self.client.get('/dashboard', follow_redirects=True)
        # Should show login page
        self.assertIn(b'Sign In', response.data)
    
    # ---------- PROJECT TESTS ----------
    
    def test_create_project(self):
        """Test project creation"""
        self._login_user1()
        
        with self.app.app_context():
            response = self.client.post('/create_project', data={
                'title': 'New Test Project',
                'description': 'Project description here',
                'stage': 'idea',
                'support': 'Need developers'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            
            # Verify project was created
            project = Project.query.filter_by(title='New Test Project').first()
            self.assertIsNotNone(project)
            self.assertEqual(project.user_id, self.user1_id)
            self.assertEqual(project.description, 'Project description here')
    
    def test_project_owner_can_add_update(self):
        """Test that project owner can add updates"""
        self._login_user1()
        
        with self.app.app_context():
            response = self.client.post(f'/project/{self.project_id}', data={
                'update': 'New update from owner'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            
            # Verify update was added
            update = Update.query.filter_by(content='New update from owner').first()
            self.assertIsNotNone(update)
            self.assertEqual(update.user_id, self.user1_id)
            self.assertEqual(update.project_id, self.project_id)
    
    def test_collaborator_can_add_update(self):
        """Test that collaborators can add updates"""
        self._login_user2()
        
        with self.app.app_context():
            response = self.client.post(f'/project/{self.project_id}', data={
                'update': 'Update from collaborator'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            
            # Verify update was added
            update = Update.query.filter_by(content='Update from collaborator').first()
            self.assertIsNotNone(update)
            self.assertEqual(update.user_id, self.user2_id)
    
    def test_non_collaborator_cannot_add_update(self):
        """Test that non-collaborators cannot add updates"""
        # Create third user who is not collaborator
        with self.app.app_context():
            user3 = User(
                username="testuser3",
                email="test3@example.com", 
                password=generate_password_hash("password789")
            )
            db.session.add(user3)
            db.session.commit()
            user3_id = user3.id
        
        # Login as user3
        self.client.post('/login', data={
            'email': 'test3@example.com',
            'password': 'password789'
        }, follow_redirects=True)
        
        with self.app.app_context():
            response = self.client.post(f'/project/{self.project_id}', data={
                'update': 'Should not work'
            }, follow_redirects=True)
            
            self.assertIn(b'Only the project owner or collaborators can add updates', response.data)
    
    # ---------- COLLABORATION TESTS ----------
    
    def test_collaborate_on_project(self):
        """Test collaboration request functionality"""
        self._login_user2()
        
        with self.app.app_context():
            # Create new project for testing collaboration
            new_project = Project(
                title="Collab Test Project",
                description="Need collaborators",
                stage="planning",
                user_id=self.user1_id
            )
            db.session.add(new_project)
            db.session.commit()
            new_project_id = new_project.id
            
            response = self.client.get(f'/collaborate/{new_project_id}', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            
            # Verify collaboration was created
            collab = Collaboration.query.filter_by(
                project_id=new_project_id,
                user_id=self.user2_id
            ).first()
            self.assertIsNotNone(collab)
    
    def test_cannot_collaborate_on_own_project(self):
        """Test that users cannot collaborate on their own projects"""
        self._login_user1()
        
        with self.app.app_context():
            response = self.client.get(f'/collaborate/{self.project_id}', follow_redirects=True)
            self.assertIn(b'You can\'t collaborate on your own project', response.data)
    
    # ---------- FEED TESTS ----------
    
    def test_feed_shows_active_projects(self):
        """Test that feed shows only active (non-completed) projects"""
        self._login_user1()
        
        with self.app.app_context():
            # Create completed project
            completed_project = Project(
                title="Completed Project",
                description="Already done",
                user_id=self.user2_id,
                completed=True,
                completed_at=datetime.utcnow()
            )
            db.session.add(completed_project)
            db.session.commit()
            
            response = self.client.get('/feed')
            self.assertEqual(response.status_code, 200)
            
            # Should show test project but not completed project
            response_data = response.data.decode('utf-8')
            self.assertIn('Test Project', response_data)
            self.assertNotIn('Completed Project', response_data)
    
    # ---------- COMPLETION TESTS ----------
    
    def test_complete_project(self):
        """Test project completion functionality"""
        self._login_user1()
        
        with self.app.app_context():
            response = self.client.get(f'/complete/{self.project_id}', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            
            # Verify project is marked as completed
            completed_project = Project.query.get(self.project_id)
            self.assertTrue(completed_project.completed)
            self.assertIsNotNone(completed_project.completed_at)
            
            # Should redirect to celebration page
            self.assertIn(b'celebration', response.data.lower())
    
    def test_non_owner_cannot_complete_project(self):
        """Test that only project owners can mark projects as complete"""
        self._login_user2()
        
        with self.app.app_context():
            response = self.client.get(f'/complete/{self.project_id}', follow_redirects=True)
            self.assertIn(b'Not authorized', response.data)
            
            # Verify project is still not completed
            project = Project.query.get(self.project_id)
            self.assertFalse(project.completed)
    
    # ---------- RELATIONSHIP TESTS ----------
    
    def test_user_project_relationship(self):
        """Test relationship between users and projects"""
        with self.app.app_context():
            user = User.query.get(self.user1_id)
            self.assertEqual(len(user.projects), 1)
            self.assertEqual(user.projects[0].title, 'Test Project')
    
    def test_project_update_relationship(self):
        """Test relationship between projects and updates"""
        with self.app.app_context():
            project = Project.query.get(self.project_id)
            self.assertEqual(len(project.updates), 1)
            self.assertEqual(project.updates[0].content, 'Test update content')
    
    def test_project_comment_relationship(self):
        """Test relationship between projects and comments"""
        with self.app.app_context():
            project = Project.query.get(self.project_id)
            self.assertEqual(len(project.comments), 1)
            self.assertEqual(project.comments[0].content, 'Test comment')
    
    def test_unique_collaboration_constraint(self):
        """Test that duplicate collaborations are prevented"""
        with self.app.app_context():
            # Try to create duplicate collaboration
            duplicate_collab = Collaboration(
                project_id=self.project_id,
                user_id=self.user2_id
            )
            db.session.add(duplicate_collab)
            
            # Should raise integrity error
            with self.assertRaises(Exception):
                db.session.commit()
            db.session.rollback()


# You need to add this function to your app.py to make routes importable
def register_routes(app):
    """Register all routes with the app"""
    from flask import render_template, redirect, url_for, request, flash
    from flask_login import login_user, logout_user, login_required, current_user
    from werkzeug.security import check_password_hash
    from datetime import datetime
    
    # Copy all your route definitions here
    # OR better: modify your app.py to make it importable
    
    @app.route("/")
    def home():
        # ... your home route code
        pass
    
    # ... all other routes


if __name__ == '__main__':
    # To run tests: python test_app.py
    unittest.main(verbosity=2)