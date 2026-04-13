# test_app_fixed.py
import unittest
import tempfile
import os
from app import app, db
from models import User, Project, Update, Comment, Collaboration
from werkzeug.security import generate_password_hash

class TestDevCollab(unittest.TestCase):
    """Test suite for DevCollab application"""
    
    def setUp(self):
        """Set up test database and client"""
        # Use in-memory database for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['LOGIN_DISABLED'] = False
        
        self.app = app
        self.client = app.test_client()
        
        with app.app_context():
            db.create_all()
            self._create_test_data()
    
    def tearDown(self):
        """Clean up after tests"""
        with app.app_context():
            db.session.remove()
            db.drop_all()
    
    def _create_test_data(self):
        """Create test users and projects"""
        # Create test users
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
        
        # Create test project
        self.project = Project(
            title="Test Project",
            description="Test Description",
            stage="development",
            support_needed="Testing help",
            user_id=self.user1.id
        )
        db.session.add(self.project)
        db.session.commit()
        
        # Create test collaboration
        self.collab = Collaboration(
            project_id=self.project.id,
            user_id=self.user2.id
        )
        db.session.add(self.collab)
        db.session.commit()
    
    def _login(self, email, password):
        """Helper to login a user"""
        return self.client.post('/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)
    
    # ---------- CRITICAL TESTS ----------
    
    def test_1_user_registration(self):
        """Test user registration"""
        response = self.client.post('/register', data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Account created', response.data)
        
        with app.app_context():
            user = User.query.filter_by(email='new@example.com').first()
            self.assertIsNotNone(user)
    
    def test_2_user_login(self):
        """Test user login"""
        response = self._login('test1@example.com', 'password123')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)
    
    def test_3_create_project(self):
        """Test project creation"""
        self._login('test1@example.com', 'password123')
        
        response = self.client.post('/create_project', data={
            'title': 'New Project',
            'description': 'Test Description',
            'stage': 'idea',
            'support': 'Need help'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        with app.app_context():
            project = Project.query.filter_by(title='New Project').first()
            self.assertIsNotNone(project)
            self.assertEqual(project.description, 'Test Description')
    
    def test_4_add_update_as_owner(self):
        """Test project owner can add updates"""
        self._login('test1@example.com', 'password123')
        
        with app.app_context():
            response = self.client.post(f'/project/{self.project.id}', data={
                'update': 'Owner update test'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            
            update = Update.query.filter_by(content='Owner update test').first()
            self.assertIsNotNone(update)
            self.assertEqual(update.user_id, self.user1.id)
    
    def test_5_add_update_as_collaborator(self):
        """Test collaborator can add updates"""
        self._login('test2@example.com', 'password456')
        
        with app.app_context():
            response = self.client.post(f'/project/{self.project.id}', data={
                'update': 'Collaborator update test'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            
            update = Update.query.filter_by(content='Collaborator update test').first()
            self.assertIsNotNone(update)
            self.assertEqual(update.user_id, self.user2.id)
    
    def test_6_collaborate_on_project(self):
        """Test collaboration functionality"""
        # Create a new project as user1
        self._login('test1@example.com', 'password123')
        
        with app.app_context():
            new_project = Project(
                title="Collab Project",
                description="Need collab",
                user_id=self.user1.id
            )
            db.session.add(new_project)
            db.session.commit()
            project_id = new_project.id
        
        # Login as user2 and collaborate
        self._login('test2@example.com', 'password456')
        response = self.client.get(f'/collaborate/{project_id}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        with app.app_context():
            collab = Collaboration.query.filter_by(
                project_id=project_id,
                user_id=self.user2.id
            ).first()
            self.assertIsNotNone(collab)
    
    def test_7_complete_project(self):
        """Test project completion"""
        self._login('test1@example.com', 'password123')
        
        with app.app_context():
            response = self.client.get(f'/complete/{self.project.id}', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            
            completed_project = Project.query.get(self.project.id)
            self.assertTrue(completed_project.completed)
            self.assertIsNotNone(completed_project.completed_at)
    
    def test_8_feed_shows_active_projects(self):
        """Test feed shows only active projects"""
        # Create a completed project
        with app.app_context():
            completed = Project(
                title="Completed Project",
                description="Done",
                user_id=self.user2.id,
                completed=True
            )
            db.session.add(completed)
            db.session.commit()
        
        self._login('test1@example.com', 'password123')
        response = self.client.get('/feed')
        
        response_text = response.data.decode('utf-8')
        self.assertIn('Test Project', response_text)
        self.assertNotIn('Completed Project', response_text)
    
    def test_9_dashboard_shows_projects(self):
        """Test dashboard shows user's projects and collaborations"""
        self._login('test1@example.com', 'password123')
        response = self.client.get('/dashboard')
        
        self.assertEqual(response.status_code, 200)
        response_text = response.data.decode('utf-8')
        self.assertIn('Test Project', response_text)


if __name__ == '__main__':
    # Run only the critical tests
    unittest.main(verbosity=2)