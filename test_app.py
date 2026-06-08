import os
# Set environment to testing before importing Flask app
os.environ['FLASK_ENV'] = 'testing'

import unittest
import json
from app import app, db
from models import Pincode, ApiLog

class PincodeApiTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Set a test secret for rapidapi middleware
        os.environ['RAPIDAPI_PROXY_SECRET'] = 'testsecret123'
        
        self.app = app.test_client()
        
        # Create database and seed mock data
        with app.app_context():
            db.create_all()
            
            # Seed Pincode data
            p1 = Pincode(
                pincode='560001',
                post_office='Bangalore G.P.O.',
                delivery_status='Delivery',
                division='Bangalore G.P.O. division',
                region='Bangalore HQ region',
                circle='Karnataka circle',
                taluk='Bangalore North',
                district_name='Bangalore',
                state_name='Karnataka'
            )
            p2 = Pincode(
                pincode='560001',
                post_office='Vidhana Soudha',
                delivery_status='Non-Delivery',
                division='Bangalore G.P.O. division',
                region='Bangalore HQ region',
                circle='Karnataka circle',
                taluk='Bangalore North',
                district_name='Bangalore',
                state_name='Karnataka'
            )
            p3 = Pincode(
                pincode='110001',
                post_office='Connaught Place',
                delivery_status='Delivery',
                division='New Delhi Central division',
                region='Delhi region',
                circle='Delhi circle',
                taluk='New Delhi',
                district_name='New Delhi',
                state_name='Delhi'
            )
            db.session.add_all([p1, p2, p3])
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_health_check(self):
        """Test the health check endpoint (no header required)."""
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), {"status": "ok"})

    def test_middleware_missing_header(self):
        """Test that requests to /api/ without secret return 401."""
        response = self.app.get('/api/pincode/560001')
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Unauthorized', data['message'])

    def test_middleware_invalid_header(self):
        """Test that requests with an invalid header return 401."""
        headers = {'X-RapidAPI-Proxy-Secret': 'wrongsecret'}
        response = self.app.get('/api/pincode/560001', headers=headers)
        self.assertEqual(response.status_code, 401)

    def test_get_pincode_success(self):
        """Test fetching pincode details returns all post offices."""
        headers = {'X-RapidAPI-Proxy-Secret': 'testsecret123'}
        response = self.app.get('/api/pincode/560001', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']), 2)
        
        po_names = [po['post_office'] for po in data['data']]
        self.assertIn('Bangalore G.P.O.', po_names)
        self.assertIn('Vidhana Soudha', po_names)

    def test_get_pincode_not_found(self):
        """Test non-existent pincode returns 404."""
        headers = {'X-RapidAPI-Proxy-Secret': 'testsecret123'}
        response = self.app.get('/api/pincode/999999', headers=headers)
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertEqual(data['message'], "Pincode not found")

    def test_get_pincode_summary(self):
        """Test fetching summary returns first match details."""
        headers = {'X-RapidAPI-Proxy-Secret': 'testsecret123'}
        response = self.app.get('/api/pincode/560001/summary', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['state'], 'Karnataka')
        self.assertEqual(data['data']['district'], 'Bangalore')
        self.assertEqual(data['data']['taluk'], 'Bangalore North')
        self.assertEqual(data['data']['city'], 'Bangalore North')

    def test_search_district(self):
        """Test searching for district returns all matching unique pincodes."""
        headers = {'X-RapidAPI-Proxy-Secret': 'testsecret123'}
        response = self.app.get('/api/search/district/Bangalore', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['pincode'], '560001')

    def test_search_district_case_insensitive(self):
        """Test searching for district is case-insensitive."""
        headers = {'X-RapidAPI-Proxy-Secret': 'testsecret123'}
        response = self.app.get('/api/search/district/bangalore', headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_search_district_not_found(self):
        """Test searching non-existent district returns 404."""
        headers = {'X-RapidAPI-Proxy-Secret': 'testsecret123'}
        response = self.app.get('/api/search/district/Atlantis', headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_search_state(self):
        """Test searching for state returns all unique districts."""
        headers = {'X-RapidAPI-Proxy-Secret': 'testsecret123'}
        response = self.app.get('/api/search/state/Karnataka', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['data'], ['Bangalore'])

    def test_search_state_not_found(self):
        """Test searching non-existent state returns 404."""
        headers = {'X-RapidAPI-Proxy-Secret': 'testsecret123'}
        response = self.app.get('/api/search/state/Narnia', headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_api_logging(self):
        """Test that API calls are logged to database."""
        headers = {'X-RapidAPI-Proxy-Secret': 'testsecret123'}
        
        # Hit pincode details endpoint
        self.app.get('/api/pincode/110001', headers=headers)
        
        with app.app_context():
            logs = ApiLog.query.all()
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].pincode_queried, '110001')
            self.assertEqual(logs[0].endpoint, '/api/pincode/110001')

if __name__ == '__main__':
    unittest.main()
