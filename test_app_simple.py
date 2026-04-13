# test_app_simple.py
import unittest
from app import app, db
from models import User, Project, Update, Comment, Collaboration
from werkzeug.security import generate_password_hash
from datetime import datetime

class TestDevCollab(unittest.TestCase):
    """Simple test suite for DevCollab application"""
    
    def setUp(self):
        """Set up test database and client"""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['LOGIN_DISABLED'] = False
        app.config['SERVER_NAME'] = 'localhost.localdomain'
        
        self.app = app
        self.client = app.test_client()
        
        with app.app_context():
            db.create_all()
            # Store IDs instead of object references
            self.user1_id = None
            self.user2_id = None
            self.project_id = None
            self._create_test_data()
    
    def tearDown(self):
        """Clean up after tests"""
        with app.app_context():
            db.session.remove()
            db.drop_all()
    
    def _create_test_data(self):
        """Create test users and projects - store only IDs"""
        with app.app_context():
            # Create test users
            user1 = User(
                username="testuser1",
                email="test1@example.com",
                password=generate_password_hash("password123")
            )
            user2 = User(
                username="testuser2", 
                email="test2@example.com",
                password=generate_password_hash("password456")
            )
            db.session.add_all([user1, user2])
            db.session.commit()
            
            # Store user IDs
            self.user1_id = user1.id
            self.user2_id = user2.id
            
            # Create test project
            project = Project(
                title="Test Project",
                description="Test Description",
                stage="development",
                support_needed="Testing help",
                user_id=self.user1_id
            )
            db.session.add(project)
            db.session.commit()
            self.project_id = project.id
            
            # Create collaboration
            collab = Collaboration(
                project_id=self.project_id,
                user_id=self.user2_id
            )
            db.session.add(collab)
            db.session.commit()
    
    def _login(self, email, password):
        """Helper to login a user"""
        return self.client.post('/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)
    
    # ---------- TEST 1: REGISTRATION ----------
    def test_1_registration(self):
        """Test user registration"""
        response = self.client.post('/register', data={
            'username': 'brandnewuser',
            'email': 'brandnew@example.com',
            'password': 'testpass123'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Account created', response.data)
        
        with app.app_context():
            user = User.query.filter_by(email='brandnew@example.com').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.username, 'brandnewuser')
    
    # ---------- TEST 2: LOGIN ----------
    def test_2_login(self):
        """Test user login"""
        response = self._login('test1@example.com', 'password123')
        self.assertEqual(response.status_code, 200)
        # Check for dashboard or success indicator
        self.assertIn(b'Dashboard', response.data)
    
    def test_3_invalid_login(self):
        """Test invalid login"""
        response = self._login('test1@example.com', 'wrongpassword')
        self.assertIn(b'Invalid email or password', response.data)
    
    # ---------- TEST 4: CREATE PROJECT ----------
    def test_4_create_project(self):
        """Test project creation"""
        # Login first
        self._login('test1@example.com', 'password123')
        
        response = self.client.post('/create_project', data={
            'title': 'My Awesome Project',
            'description': 'This is a test project',
            'stage': 'idea',
            'support': 'Need developers'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        with app.app_context():
            project = Project.query.filter_by(title='My Awesome Project').first()
            self.assertIsNotNone(project)
            self.assertEqual(project.user_id, self.user1_id)
    
    # ---------- TEST 5: ADD UPDATE AS OWNER ----------
    def test_5_owner_add_update(self):
        """Test project owner can add updates"""
        self._login('test1@example.com', 'password123')
        
        with app.app_context():
            response = self.client.post(f'/project/{self.project_id}', data={
                'update': 'This is an update from the owner'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            
            # Verify update was added
            update = Update.query.filter_by(content='This is an update from the owner').first()
            self.assertIsNotNone(update)
            self.assertEqual(update.user_id, self.user1_id)
            self.assertEqual(update.project_id, self.project_id)
    
    # ---------- TEST 6: ADD UPDATE AS COLLABORATOR ----------
    def test_6_collaborator_add_update(self):
        """Test collaborator can add updates"""
        self._login('test2@example.com', 'password456')
        
        with app.app_context():
            response = self.client.post(f'/project/{self.project_id}', data={
                'update': 'Update from collaborator'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            
            update = Update.query.filter_by(content='Update from collaborator').first()
            self.assertIsNotNone(update)
            self.assertEqual(update.user_id, self.user2_id)
    
    # ---------- TEST 7: NON-COLLABORATOR CANNOT ADD UPDATE ----------
    def test_7_non_collaborator_cannot_update(self):
        """Test non-collaborators cannot add updates"""
        # Create a third user
        with app.app_context():
            user3 = User(
                username="testuser3",
                email="test3@example.com",
                password=generate_password_hash("password789")
            )
            db.session.add(user3)
            db.session.commit()
        
        # Login as third user
        self.client.post('/login', data={
            'email': 'test3@example.com',
            'password': 'password789'
        }, follow_redirects=True)
        
        with app.app_context():
            response = self.client.post(f'/project/{self.project_id}', data={
                'update': 'Should not work'
            }, follow_redirects=True)
            
            # Should show error message
            self.assertIn(b'Only the project owner or collaborators can add updates', response.data)
    
    # ---------- TEST 8: COLLABORATE ON PROJECT ----------
    def test_8_collaborate(self):
        """Test collaboration functionality"""
        # Create a new project as user1
        self._login('test1@example.com', 'password123')
        
        with app.app_context():
            new_project = Project(
                title="Collab Project",
                description="Need help",
                user_id=self.user1_id
            )
            db.session.add(new_project)
            db.session.commit()
            new_project_id = new_project.id
        
        # Login as user2 and collaborate
        self._login('test2@example.com', 'password456')
        response = self.client.get(f'/collaborate/{new_project_id}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        with app.app_context():
            collab = Collaboration.query.filter_by(
                project_id=new_project_id,
                user_id=self.user2_id
            ).first()
            self.assertIsNotNone(collab)
    
    # ---------- TEST 9: CANNOT COLLABORATE ON OWN PROJECT ----------
    def test_9_cannot_collaborate_own(self):
        """Test users cannot collaborate on their own projects"""
        self._login('test1@example.com', 'password123')
        
        response = self.client.get(f'/collaborate/{self.project_id}', follow_redirects=True)
        self.assertIn(b'You can\'t collaborate on your own project', response.data)
    
    # ---------- TEST 10: COMPLETE PROJECT ----------
    def test_10_complete_project(self):
        """Test project completion by owner"""
        self._login('test1@example.com', 'password123')
        
        with app.app_context():
            response = self.client.get(f'/complete/{self.project_id}', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            
            # Verify project is completed
            project = Project.query.get(self.project_id)
            self.assertTrue(project.completed)
            self.assertIsNotNone(project.completed_at)
    
    # ---------- TEST 11: NON-OWNER CANNOT COMPLETE ----------
    def test_11_non_owner_cannot_complete(self):
        """Test only owners can complete projects"""
        self._login('test2@example.com', 'password456')
        
        with app.app_context():
            response = self.client.get(f'/complete/{self.project_id}', follow_redirects=True)
            self.assertIn(b'Not authorized', response.data)
            
            # Verify project is still not completed
            project = Project.query.get(self.project_id)
            self.assertFalse(project.completed)
    
    # ---------- TEST 12: FEED SHOWS ONLY ACTIVE PROJECTS ----------
    def test_12_feed_active_only(self):
        """Test feed shows only non-completed projects"""
        # Create a completed project
        with app.app_context():
            completed = Project(
                title="Completed Project",
                description="Done",
                user_id=self.user2_id,
                completed=True,
                completed_at=datetime.utcnow()
            )
            db.session.add(completed)
            db.session.commit()
        
        self._login('test1@example.com', 'password123')
        response = self.client.get('/feed')
        
        response_text = response.data.decode('utf-8')
        self.assertIn('Test Project', response_text)
        self.assertNotIn('Completed Project', response_text)
    
    # ---------- TEST 13: DASHBOARD SHOWS PROJECTS ----------
    def test_13_dashboard(self):
        """Test dashboard shows user's projects"""
        self._login('test1@example.com', 'password123')
        response = self.client.get('/dashboard')
        
        self.assertEqual(response.status_code, 200)
        response_text = response.data.decode('utf-8')
        self.assertIn('Test Project', response_text)
    
    # ---------- TEST 14: PROTECTED ROUTES ----------
    def test_14_protected_routes(self):
        """Test protected routes require login"""
        # Try to access dashboard without login
        response = self.client.get('/dashboard', follow_redirects=True)
        # Should be redirected to login page
        self.assertIn(b'Sign In', response.data)


if __name__ == '__main__':
    # Create a test suite with only the most critical tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add only the most critical tests (order matters)
    critical_tests = [
        'test_1_registration',
        'test_2_login',
        'test_4_create_project',
        'test_5_owner_add_update',
        'test_6_collaborator_add_update',
        'test_8_collaborate',
        'test_10_complete_project',
        'test_12_feed_active_only',
        'test_13_dashboard',
    ]
    
    for test in critical_tests:
        suite.addTest(TestDevCollab(test))
    
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)