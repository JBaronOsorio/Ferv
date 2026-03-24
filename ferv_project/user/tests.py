from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from graph.models import UserPreferenceNode


class UserAuthenticationTestCase(TestCase):
    """Test user registration, login, logout flows."""
    
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('user:register')
        self.login_url = reverse('user:login')
        self.logout_url = reverse('user:logout')
        self.questionnaire_url = reverse('graph:questionnaire')
        self.graph_index_url = reverse('graph:index')

    def test_register_page_loads(self):
        """Test that registration page loads for unauthenticated users."""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/register.html')

    def test_register_creates_user(self):
        """Test that registration creates a new user."""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
        }
        response = self.client.post(self.register_url, data)
        
        user_exists = User.objects.filter(username='testuser').exists()
        self.assertTrue(user_exists)

    def test_register_with_mismatched_passwords(self):
        """Test that registration fails with mismatched passwords."""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'securepass123',
            'confirm_password': 'differentpass',
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        
        user_exists = User.objects.filter(username='testuser').exists()
        self.assertFalse(user_exists)

    def test_register_redirects_to_questionnaire(self):
        """Test that registration redirects to questionnaire after success."""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
        }
        response = self.client.post(self.register_url, data, follow=True)
        
        self.assertRedirects(response, self.questionnaire_url)

    def test_registered_user_is_logged_in(self):
        """Test that user is automatically logged in after registration."""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
        }
        self.client.post(self.register_url, data, follow=True)
        
        response = self.client.get(self.graph_index_url)
        self.assertEqual(response.status_code, 200)

    def test_login_page_loads(self):
        """Test that login page loads."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/login.html')

    def test_login_with_valid_credentials(self):
        """Test that login works with valid credentials."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='securepass123'
        )
        
        data = {
            'username': 'testuser',
            'password': 'securepass123',
        }
        response = self.client.post(self.login_url, data, follow=True)
        
        self.assertRedirects(response, self.graph_index_url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_with_invalid_credentials(self):
        """Test that login fails with invalid credentials."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='securepass123'
        )
        
        data = {
            'username': 'testuser',
            'password': 'wrongpassword',
        }
        response = self.client.post(self.login_url, data)
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_logs_out_user(self):
        """Test that logout actually logs out the user."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='securepass123'
        )
        self.client.login(username='testuser', password='securepass123')
        
        response = self.client.get(self.logout_url, follow=True)
        
        self.assertRedirects(response, self.login_url)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_authenticated_user_cannot_register(self):
        """Test that authenticated user is redirected from register."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='securepass123'
        )
        self.client.login(username='testuser', password='securepass123')
        
        response = self.client.get(self.register_url, follow=True)
        
        self.assertRedirects(response, self.questionnaire_url)

    def test_authenticated_user_cannot_login(self):
        """Test that authenticated user is redirected from login."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='securepass123'
        )
        self.client.login(username='testuser', password='securepass123')
        
        response = self.client.get(self.login_url, follow=True)
        
        self.assertRedirects(response, self.graph_index_url)


class GraphQuestionnaireTestCase(TestCase):
    """Test questionnaire and graph preference nodes."""
    
    def setUp(self):
        self.client = Client()
        self.questionnaire_url = reverse('graph:questionnaire')
        self.graph_index_url = reverse('graph:index')
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='securepass123'
        )

    def test_unauthenticated_user_redirected_to_login(self):
        """Test that unauthenticated users are redirected to login."""
        response = self.client.get(self.questionnaire_url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/user/login/', response.url)

    def test_authenticated_user_can_access_questionnaire(self):
        """Test that authenticated users can access questionnaire."""
        self.client.login(username='testuser', password='securepass123')
        
        response = self.client.get(self.questionnaire_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'graph/questionnaire.html')

    def test_submit_questionnaire_creates_preference_nodes(self):
        """Test that submitting questionnaire creates preference nodes."""
        self.client.login(username='testuser', password='securepass123')
        
        data = {
            'place_types': ['bars', 'cafes'],
            'ambiences': ['quiet', 'intimate'],
            'activities': ['reading', 'live_music'],
            'budget_range': 'medium',
        }
        response = self.client.post(self.questionnaire_url, data, follow=True)
        
        nodes = UserPreferenceNode.objects.filter(user=self.user)
        self.assertEqual(nodes.count(), 7)

    def test_questionnaire_creates_correct_categories(self):
        """Test that questionnaire nodes have correct categories."""
        self.client.login(username='testuser', password='securepass123')
        
        data = {
            'place_types': ['bars'],
            'ambiences': ['quiet'],
            'activities': ['reading'],
            'budget_range': 'medium',
        }
        self.client.post(self.questionnaire_url, data)
        
        place_type_nodes = UserPreferenceNode.objects.filter(
            user=self.user,
            category=UserPreferenceNode.CATEGORY_PLACE_TYPE
        )
        ambience_nodes = UserPreferenceNode.objects.filter(
            user=self.user,
            category=UserPreferenceNode.CATEGORY_AMBIENCE
        )
        activity_nodes = UserPreferenceNode.objects.filter(
            user=self.user,
            category=UserPreferenceNode.CATEGORY_ACTIVITY
        )
        budget_nodes = UserPreferenceNode.objects.filter(
            user=self.user,
            category=UserPreferenceNode.CATEGORY_BUDGET
        )
        
        self.assertEqual(place_type_nodes.count(), 1)
        self.assertEqual(ambience_nodes.count(), 1)
        self.assertEqual(activity_nodes.count(), 1)
        self.assertEqual(budget_nodes.count(), 1)

    def test_questionnaire_redirects_to_graph(self):
        """Test that successful questionnaire submission redirects to graph."""
        self.client.login(username='testuser', password='securepass123')
        
        data = {
            'place_types': ['bars'],
            'ambiences': ['quiet'],
            'activities': ['reading'],
            'budget_range': 'medium',
        }
        response = self.client.post(self.questionnaire_url, data, follow=True)
        
        self.assertRedirects(response, self.graph_index_url)

    def test_existing_preferences_are_replaced(self):
        """Test that submitting questionnaire again replaces old preferences."""
        self.client.login(username='testuser', password='securepass123')
        
        data_1 = {
            'place_types': ['bars'],
            'ambiences': ['quiet'],
            'activities': ['reading'],
            'budget_range': 'medium',
        }
        self.client.post(self.questionnaire_url, data_1)
        
        initial_count = UserPreferenceNode.objects.filter(user=self.user).count()
        
        data_2 = {
            'place_types': ['cafes', 'restaurants'],
            'ambiences': ['lively', 'family_friendly'],
            'activities': ['socializing', 'outdoor_walks'],
            'budget_range': 'high',
        }
        self.client.post(self.questionnaire_url, data_2)
        
        final_count = UserPreferenceNode.objects.filter(user=self.user).count()
        
        self.assertEqual(final_count, 7)

    def test_graph_index_displays_preference_nodes(self):
        """Test that graph index page displays user preference nodes."""
        self.client.login(username='testuser', password='securepass123')
        
        data = {
            'place_types': ['bars'],
            'ambiences': ['quiet'],
            'activities': ['reading'],
            'budget_range': 'medium',
        }
        self.client.post(self.questionnaire_url, data)
        
        response = self.client.get(self.graph_index_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bars')
        self.assertContains(response, 'quiet')


class EndToEndFlowTestCase(TestCase):
    """Test complete flow from registration to graph visualization."""
    
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('user:register')
        self.login_url = reverse('user:login')
        self.questionnaire_url = reverse('graph:questionnaire')
        self.graph_index_url = reverse('graph:index')

    def test_complete_flow_new_user(self):
        """Test complete flow: register -> questionnaire -> graph."""
        register_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
        }
        self.client.post(self.register_url, register_data)
        
        questionnaire_data = {
            'place_types': ['bars', 'cafes'],
            'ambiences': ['quiet', 'lively'],
            'activities': ['reading', 'socializing'],
            'budget_range': 'medium',
        }
        response = self.client.post(self.questionnaire_url, questionnaire_data)
        
        graph_response = self.client.get(self.graph_index_url)
        
        self.assertEqual(graph_response.status_code, 200)
        
        user = User.objects.get(username='newuser')
        preference_nodes = UserPreferenceNode.objects.filter(user=user)
        self.assertEqual(preference_nodes.count(), 7)

    def test_complete_flow_existing_user(self):
        """Test complete flow: login -> questionnaire -> graph."""
        user = User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='securepass123'
        )
        
        login_data = {
            'username': 'existinguser',
            'password': 'securepass123',
        }
        self.client.post(self.login_url, login_data)
        
        questionnaire_data = {
            'place_types': ['restaurants'],
            'ambiences': ['family_friendly'],
            'activities': ['outdoor_walks'],
            'budget_range': 'low',
        }
        self.client.post(self.questionnaire_url, questionnaire_data)
        
        graph_response = self.client.get(self.graph_index_url)
        
        self.assertEqual(graph_response.status_code, 200)
        
        preference_nodes = UserPreferenceNode.objects.filter(user=user)
        self.assertEqual(preference_nodes.count(), 4)
