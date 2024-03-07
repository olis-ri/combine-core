from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase
from django.urls import reverse

from core.models import Transformation
from tests.utils import TestConfiguration


class TransformationTestCase(TestCase):
    XSLT_PAYLOAD = '''<?xml version="1.0" encoding="UTF-8"?>
    <xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="2.0">
        <xsl:output method="xml" indent="yes"/>

        <xsl:template match="/">
            <xsl:call-template name="foo"/>
        </xsl:template>

        <xsl:template name="foo">
            <bar>
                <xsl:value-of select="*/foo"/>
            </bar>
        </xsl:template>
    </xsl:stylesheet>'''

    PYTHON_PAYLOAD = '''from lxml import etree
    def python_record_transformation(record):
        foo_elem_query = record.xml.xpath('foo', namespaces=record.nsmap)
        foo_elem = foo_elem_query[0]
        foo_elem.attrib['type'] = 'bar'
        return [etree.tostring(record.xml), '', True]
    '''

    def setUp(self):
        self.config = TestConfiguration()
        self.client.force_login(self.config.user)  # The configuration page requires login

    def test_create_transformation_scenario_get(self):
        response = self.client.get(reverse('create_transformation_scenario'))
        self.assertIn(b'Create new Transformation Scenario', response.content)
        self.assertNotIn(b'Python Code Snippet', response.content)

    def test_create_permitted_python_transformation_scenario_get(self):
        with self.settings(ENABLE_PYTHON='true'):
            response = self.client.get(reverse('create_transformation_scenario'))
            self.assertIn(b'Create new Transformation Scenario', response.content)
            self.assertIn(b'Python Code Snippet', response.content)

    def test_create_transformation_scenario_post(self):
        post_body = {
            'name': 'Test Transform',
            'payload': 'test payload',
            'transformation_type': 'openrefine'
        }
        response = self.client.post(reverse('create_transformation_scenario'), post_body)
        self.assertRedirects(response, reverse('configuration'))
        transform = Transformation.objects.get(name='Test Transform')
        self.assertIsNotNone(transform.id)
        transform_dict = transform.as_dict()
        for item in post_body:
            self.assertEqual(transform_dict[item], post_body[item])

    def test_create_python_transformation_scenario_post(self):
        post_body = {
            'name': 'Test Transform',
            'payload': 'test payload',
            'transformation_type': 'python'
        }
        response = self.client.post(reverse('create_transformation_scenario'), post_body)
        self.assertIn(b'Select a valid choice', response.content)

    def test_create_permitted_python_transformation_scenario_post(self):
        with self.settings(ENABLE_PYTHON='true'):
            post_body = {
                'name': 'Test Transform',
                'payload': 'test payload',
                'transformation_type': 'python'
            }
            response = self.client.post(reverse('create_transformation_scenario'), post_body)
            self.assertRedirects(response, reverse('configuration'))
            transform = Transformation.objects.get(name='Test Transform')
            self.assertIsNotNone(transform.id)
            transform_dict = transform.as_dict()
            for item in post_body:
                self.assertEqual(transform_dict[item], post_body[item])

    def test_create_transformation_scenario_invalid(self):
        response = self.client.post(reverse('create_transformation_scenario'), {})
        self.assertIn(b'This field is required.', response.content)

    def test_edit_transformation_scenario_get(self):
        transformation = Transformation.objects.create(
            name='Test Transform',
            payload='test payload',
            transformation_type='openrefine')
        response = self.client.get(reverse('transformation_scenario', args=[transformation.id]))
        self.assertIn(b'Test Transform', response.content)

    def test_edit_python_transformation_scenario_get(self):
        transformation = Transformation.objects.create(
            name='Test Transform',
            payload='test payload',
            transformation_type='python')
        response = self.client.get(reverse('transformation_scenario', args=[transformation.id]))
        self.assertIn(b'Select a valid choice. python is not one of the available choices', response.content)

    def test_edit_permitted_python_transformation_scenario_get(self):
        with self.settings(ENABLE_PYTHON='true'):
            transformation = Transformation.objects.create(
                name='Test Transform',
                payload='test payload',
                transformation_type='python')
            response = self.client.get(reverse('transformation_scenario', args=[transformation.id]))
            self.assertNotIn(b'Select a valid choice. python is not one of the available choices', response.content)

    def test_edit_transformation_scenario_post(self):
        transformation = Transformation.objects.create(
            name='Test Transform',
            payload='test payload',
            transformation_type='openrefine')
        response = self.client.post(reverse('transformation_scenario', args=[transformation.id]), {
            'payload': 'some other payload',
            'name': transformation.name,
            'transformation_type': transformation.transformation_type
        })
        self.assertRedirects(response, reverse('configuration'))
        transform = Transformation.objects.get(name='Test Transform')
        self.assertIsNotNone(transform.id)
        self.assertEqual(transform.payload, 'some other payload')
        self.assertEqual(transform.transformation_type, 'openrefine')

    def test_edit_python_transformation_scenario_post(self):
        transformation = Transformation.objects.create(
            name='Test Transform',
            payload='test payload',
            transformation_type='python')
        response = self.client.post(reverse('transformation_scenario', args=[transformation.id]), {
            'payload': 'some other payload',
            'name': transformation.name,
            'transformation_type': transformation.transformation_type
        })
        self.assertIn(b'Select a valid choice. python is not one of the available choices', response.content)

    def test_edit_permitted_python_transformation_scenario_post(self):
        with self.settings(ENABLE_PYTHON='true'):
            transformation = Transformation.objects.create(
                name='Test Transform',
                payload='test payload',
                transformation_type='python')
            response = self.client.post(reverse('transformation_scenario', args=[transformation.id]), {
                'payload': 'some other payload',
                'name': transformation.name,
                'transformation_type': transformation.transformation_type
            })
            self.assertRedirects(response, reverse('configuration'))
            transform = Transformation.objects.get(name='Test Transform')
            self.assertIsNotNone(transform.id)
            self.assertEqual(transform.payload, 'some other payload')
            self.assertEqual(transform.transformation_type, 'python')

    def test_edit_transformation_scenario_invalid(self):
        transformation = Transformation.objects.create(
            name='Test Transform',
            payload='test payload',
            transformation_type='python')
        response = self.client.post(reverse('transformation_scenario', args=[transformation.id]), {
            'payload': 'some other payload',
        })
        self.assertIn(b'This field is required.', response.content)

    def test_transformation_scenario_delete(self):
        transformation = Transformation.objects.create(
            name='Test Transform',
            payload='test payload',
            transformation_type='python')
        response = self.client.delete(reverse('delete_transformation_scenario', args=[transformation.id]))
        self.assertRedirects(response, reverse('configuration'))
        with self.assertRaises(ObjectDoesNotExist):
            Transformation.objects.get(pk=int(transformation.id))

    def test_transformation_scenario_delete_nonexistent(self):
        response = self.client.delete(reverse('delete_transformation_scenario', args=[12345]))
        self.assertRedirects(response, reverse('configuration'))

    def test_transformation_scenario_payload(self):
        transformation = Transformation.objects.create(name='Test Transform',
                                                       payload='test payload',
                                                       transformation_type='python')
        response = self.client.get(reverse('transformation_scenario_payload', args=[transformation.id]))
        self.assertEqual(b'test payload', response.content)

    def test_get_test_transformation(self):
        response = self.client.get(reverse('test_transformation_scenario'))
        self.assertIn(b'Select a pre-existing Transformation Scenario', response.content)
        self.assertNotIn(b'Python Code Snippet', response.content)

    def test_get_test_transformation_python_permitted(self):
        with self.settings(ENABLE_PYTHON='true'):
            response = self.client.get(reverse('test_transformation_scenario'))
            self.assertIn(b'Select a pre-existing Transformation Scenario', response.content)
            self.assertIn(b'Python Code Snippet', response.content)

    def test_post_test_transformation(self):
        post_body = {
            'trans_test_type': 'single',
            'trans_type': 'xslt',
            'trans_payload': self.XSLT_PAYLOAD,
            'db_id': self.config.record.id
        }
        #response = self.client.post(reverse('test_transformation_scenario'), post_body)
        #print(response.json())
        # encountering difficulty running this test with docker up; pyjxslt doesn't like
        # requests coming across the docker barrier? it works manually tested though
        pass

    def test_post_test_transformation_python(self):
        post_body = {
            'trans_test_type': 'single',
            'trans_type': 'python',
            'trans_payload': self.PYTHON_PAYLOAD,
            'db_id': self.config.record.id
        }
        response = self.client.post(reverse('test_transformation_scenario'), post_body)
        self.assertEqual(b'requested invalid type for transformation scenario: python', response.content)

    def test_post_test_transformation_python_permitted(self):
        # assuming this is going to have the same issues as above w/ pyjxslt
        pass
