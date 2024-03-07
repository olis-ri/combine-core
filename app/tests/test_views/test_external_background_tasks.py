from django.test import TestCase

from core.models import LivySession
from tests.utils import TestConfiguration


class ExternalBackgroundTaskTestCase(TestCase):
    def setUp(self):
        self.config = TestConfiguration()
        self.client.force_login(self.config.user)

    def test_get_system(self):
        response = self.client.get('/combine/system')
        self.assertIn(b'Livy/Spark Session', response.content)
        self.assertIn(b'Background Tasks', response.content)

    def test_livy_session_start(self):
        response = self.client.get('/combine/system/livy_sessions/start')
        self.assertRedirects(response, '/combine/system')
        response = self.client.get(response.url)
        self.assertIn(b'Livy Session, sessionId', response.content)
        self.assertIn(b'starting', response.content)

    def test_livy_session_stop(self):
        livy_session = LivySession()
        livy_session.start_session()
        livy_session.save()
        response = self.client.get(f'/combine/system/livy_sessions/{livy_session.session_id}/stop')
        self.assertRedirects(response, '/combine/system')

    def test_system_bg_status(self):
        response = self.client.get('/combine/system/bg_status')
        json = response.json()
        self.assertEqual(json['celery_status'], 'unknown')
        self.assertEqual(json['livy_status'], 'stopped')
