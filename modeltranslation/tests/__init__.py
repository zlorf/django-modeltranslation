# -*- coding: utf-8 -*-
"""
Tests have to be run with modeltranslation.tests.settings:
./manage.py test --settings=modeltranslation.tests.settings modeltranslation

A testrunner is provided that can be run from the source directory:
python modeltranslation/tests/runtests.py

TODO: Merge autoregister tests from django-modeltranslation-wrapper.
"""
from django import forms
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import Q, F
from django.db.models.loading import AppCache
from django.test import TestCase
from django.utils.datastructures import SortedDict
from django.utils.translation import get_language
from django.utils.translation import trans_real

from modeltranslation import settings as mt_settings
from modeltranslation import translator
from modeltranslation.admin import (TranslationAdmin,
                                    TranslationStackedInline)
from modeltranslation.tests.models import (
    DataModel, TestModel, FallbackTestModel, FallbackTestModel2,
    FileFieldsModel, AbstractModelB, MultitableModelA,
    MultitableModelB, MultitableModelC, MultitableModelD,
    CustomManagerModel)
from modeltranslation.tests.translation import FallbackTranslationOptions2


# None of the following tests really depend on the content of the request,
# so we'll just pass in None.
request = None


class ModeltranslationTestBase(TestCase):
    urls = 'modeltranslation.tests.urls'
    cache = AppCache()

    @classmethod
    def clear_cache(cls):
        """
        It is necessary to clear cache - otherwise model reloading won't
        recreate models, but just use old ones.
        """
        cls.cache.app_store = SortedDict()
        cls.cache.app_models = SortedDict()
        cls.cache.app_errors = {}
        cls.cache.handled = {}
        cls.cache.loaded = False

    @classmethod
    def reset_cache(cls):
        """
        Rebuild whole cache, import all models again
        """
        cls.clear_cache()
        cls.cache._populate()
        for m in cls.cache.get_apps():
            reload(m)

    def setUp(self):
        trans_real.activate('de')

    def tearDown(self):
        trans_real.deactivate()


class ModeltranslationTest(ModeltranslationTestBase):
    """
    Basic tests for the modeltranslation application.
    """
    def test_registration(self):
        self.client.post('/set_language/', data={'language': 'de'})
        #self.client.session['django_language'] = 'de-de'
        #self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'de-de'

        langs = tuple(l for l in mt_settings.AVAILABLE_LANGUAGES)
        self.failUnlessEqual(2, len(langs))
        self.failUnless('de' in langs)
        self.failUnless('en' in langs)
        self.failUnless(translator.translator)

        # Check that eight models are registered for translation
        self.failUnlessEqual(len(translator.translator._registry), 10)

        # Try to unregister a model that is not registered
        self.assertRaises(translator.NotRegistered,
                          translator.translator.unregister, User)

        # Try to get options for a model that is not registered
        self.assertRaises(translator.NotRegistered,
                          translator.translator.get_options_for_model, User)

    def test_translated_models(self):
        # First create an instance of the test model to play with
        inst = TestModel.objects.create(title="Testtitle", text="Testtext")
        field_names = dir(inst)
        self.failUnless('id' in field_names)
        self.failUnless('title' in field_names)
        self.failUnless('title_en' in field_names)
        self.failUnless('text' in field_names)
        self.failUnless('text_en' in field_names)
        self.failUnless('url' in field_names)
        self.failUnless('url_en' in field_names)
        self.failUnless('email' in field_names)
        self.failUnless('email_en' in field_names)
        inst.delete()

    def test_queryset(self):
        self.failUnlessEqual(get_language(), 'de')
        title_de = 'title de'
        title_en = 'title en'

        obj = TestModel.objects.create(title=title_de)
        self.failUnlessEqual(obj.title, title_de)
        qs = TestModel.objects.filter(title=title_de)
        self.failUnlessEqual(qs[0].title, title_de)
        self.failUnlessEqual(qs[0].title_en, None)
        qs = TestModel.objects.filter(title__startswith='title d')
        self.failUnlessEqual(qs[0].title, title_de)
        obj.delete()

        obj = TestModel.objects.create(title_en=title_en)
        qs = TestModel.objects.filter(title_en=title_en)
        self.failUnlessEqual(qs[0].title_en, title_en)
        # TODO: Do we really expect an empty string or None?
        self.failUnlessEqual(qs[0].title, '')
        qs = TestModel.objects.filter(title_en__startswith='title e')
        self.failUnlessEqual(qs[0].title_en, title_en)
        obj.delete()

        trans_real.activate('en')
        self.failUnlessEqual(get_language(), 'en')
        obj = TestModel.objects.create(title=title_en)
        self.failUnlessEqual(obj.title, title_en)
        qs = TestModel.objects.filter(title=title_en)
        obj.delete()

    def test_order_by(self):
        trans_real.activate('de')
        self.failUnlessEqual(get_language(), 'de')
        TestModel.objects.create(title_en='b')
        TestModel.objects.create(title_en='a')
        TestModel.objects.create(title_en='c')
        qs = TestModel.objects.all().order_by('title')
        # Note: The title field reflects the default language ('de').
        # First ensure german title have no values (we didn't set any).
        self.failUnlessEqual(qs[0].title, '')
        self.failUnlessEqual(qs[1].title, '')
        self.failUnlessEqual(qs[2].title, '')
        # Because the current language is also german, ordering should simply
        # happen on this field, nothing special, because they are empty we
        # expect the queryset to be ordered by id.
        self.failUnlessEqual(qs[0].title_en, 'b')
        self.failUnlessEqual(qs[1].title_en, 'a')
        self.failUnlessEqual(qs[2].title_en, 'c')

        # Now switch to ``en`` and order by the original field again.
        trans_real.activate('en')
        qs = TestModel.objects.all().order_by('title')
        # This time we expect, as the queryset is aware of the current
        # language, to be ordered by the ``title_en`` field.
        self.failUnlessEqual(qs[0].title_en, 'a')
        self.failUnlessEqual(qs[1].title_en, 'b')
        self.failUnlessEqual(qs[2].title_en, 'c')

    def test_verbose_name(self):
        inst = TestModel.objects.create(title="Testtitle", text="Testtext")
        self.assertEquals(unicode(
            inst._meta.get_field('title_en').verbose_name), u'title [en]')
        inst.delete()

    def test_set_translation(self):
        self.failUnlessEqual(get_language(), 'de')
        # First create an instance of the test model to play with
        title1_de = "title de"
        title1_en = "title en"
        title2_de = "title2 de"
        inst1 = TestModel(title_en=title1_en, text="Testtext")
        inst1.title = title1_de
        inst2 = TestModel(title=title2_de, text="Testtext")
        inst1.save()
        inst2.save()

        self.failUnlessEqual(inst1.title, title1_de)
        self.failUnlessEqual(inst1.title_en, title1_en)

        self.failUnlessEqual(inst2.title, title2_de)
        self.failUnlessEqual(inst2.title_en, None)

        del inst1
        del inst2

        # Check that the translation fields are correctly saved and provide the
        # correct value when retrieving them again.
        n = TestModel.objects.get(title=title1_de)
        self.failUnlessEqual(n.title, title1_de)
        self.failUnlessEqual(n.title_en, title1_en)

    def test_fallback_values_1(self):
        """
        If ``fallback_values`` is set to string, all untranslated fields would
        return this string.
        """
        title1_de = "title de"
        n = FallbackTestModel()
        n.title = title1_de
        n.save()
        del n
        n = FallbackTestModel.objects.get(title=title1_de)
        self.failUnlessEqual(n.title, title1_de)
        trans_real.activate("en")
        self.failUnlessEqual(n.title, "")

    def test_fallback_values_2(self):
        """
        If ``fallback_values`` is set to ``dict``, all untranslated fields in
        ``dict`` would return this mapped value. Fields not in ``dict`` would
        return default translation.
        """
        title1_de = "title de"
        text1_de = "text in german"
        n = FallbackTestModel2()
        n.title = title1_de
        n.text = text1_de
        n.save()
        del n
        n = FallbackTestModel2.objects.get(title=title1_de)
        trans_real.activate("en")
        self.failUnlessEqual(n.title, title1_de)
        self.failUnlessEqual(
            n.text, FallbackTranslationOptions2.fallback_values['text'])


class FileFieldsTest(ModeltranslationTestBase):
    def test_file_fields(self):
        n = FileFieldsModel.objects.create(title='Testtitle', file=None)

        field_names = dir(n)
        self.failUnless('title' in field_names)
        self.failUnless('title_en' in field_names)
        self.failUnless('file' in field_names)
        self.failUnless('file_en' in field_names)
        self.failUnless('image' in field_names)
        self.failUnless('image_en' in field_names)

        n.delete()

    def test_file_field_instances(self):
        n = FileFieldsModel(title='Testtitle', file=None)

        trans_real.activate('en')
        n.title = 'title en'
        n.file = 'a_en'

        #n.file_en.save('b_en', ContentFile('file in english'))
        n.file.save('b_en', ContentFile('file in english'))
        n.image = 'i_en.jpg'
        n.image.save('i_en.jpg', ContentFile('image in english'))

        trans_real.activate('de')
        n.title = 'title de'
        n.file = 'a_de'
        n.file.save('b_de', ContentFile('file in german'))
        n.image = 'i_de.jpg'
        n.image.save('i_de.jpg', ContentFile('image in germany'))

        n.save()

        trans_real.activate('en')
        #self.failUnlessEqual(n.title, 'title_en')
        self.failUnless(n.file.name.count('b_en') > 0)
        self.failUnless(n.image.name.count('i_en') > 0)

        trans_real.activate('de')
        #self.failUnlessEqual(n.title, 'title_de')
        self.failUnless(n.file.name.count('b_de') > 0)
        self.failUnless(n.image.name.count('i_de') > 0)

        n.file_en.delete()
        n.image_en.delete()
        n.file.delete()
        n.image.delete()

        n.delete()


class TranslationDescriptorTest(ModeltranslationTestBase):
    """
    Reading the value from the original field returns the value in translated
    to the current language.
    """
    def _test_field(self, field_name, value_de, value_en, deactivate=True):
        field_name_en = '%s_en' % field_name
        params = {'title': 'title de', 'title_en': 'title en',
                  field_name: value_de, field_name_en: value_en}

        n = TestModel.objects.create(**params)
        # Language is set to 'de' at this point
        self.failUnlessEqual(get_language(), 'de')
        self.failUnlessEqual(getattr(n, field_name), value_de)
        self.failUnlessEqual(getattr(n, field_name_en), value_en)
        # Now switch to "en"
        trans_real.activate("en")
        self.failUnlessEqual(get_language(), "en")
        # Should now be return the english one (just by switching the language)
        self.failUnlessEqual(getattr(n, field_name), value_en)

        n = TestModel.objects.create(**params)
        n.save()
        # Language is set to "en" at this point
        self.failUnlessEqual(getattr(n, field_name), value_en)
        self.failUnlessEqual(getattr(n, field_name_en), value_en)
        trans_real.activate('de')
        self.failUnlessEqual(get_language(), 'de')
        self.failUnlessEqual(getattr(n, field_name), value_de)

        if deactivate:
            trans_real.deactivate()

    def test_descriptor(self):
        """
        Basic CharField/TextField test.
        Could as well call _test_field, just kept for reference.
        """
        title1_de = "title de"
        title1_en = "title en"
        text_de = "Dies ist ein deutscher Satz"
        text_en = "This is an english sentence"

        n = TestModel.objects.create(title=title1_de, title_en=title1_en,
                                     text=text_de, text_en=text_en)
        n.save()

        # Language is set to 'de' at this point
        self.failUnlessEqual(get_language(), 'de')
        self.failUnlessEqual(n.title, title1_de)
        self.failUnlessEqual(n.title_en, title1_en)
        self.failUnlessEqual(n.text, text_de)
        self.failUnlessEqual(n.text_en, text_en)
        # Now switch to "en"
        trans_real.activate("en")
        self.failUnlessEqual(get_language(), "en")
        # Title should now be return the english one (just by switching the
        # language)
        self.failUnlessEqual(n.title, title1_en)
        self.failUnlessEqual(n.text, text_en)

        n = TestModel.objects.create(title=title1_de, title_en=title1_en,
                                     text=text_de, text_en=text_en)
        n.save()
        # Language is set to "en" at this point
        self.failUnlessEqual(n.title, title1_en)
        self.failUnlessEqual(n.title_en, title1_en)
        self.failUnlessEqual(n.text, text_en)
        self.failUnlessEqual(n.text_en, text_en)
        trans_real.activate('de')
        self.failUnlessEqual(get_language(), 'de')
        self.failUnlessEqual(n.title, title1_de)
        self.failUnlessEqual(n.text, text_de)

        trans_real.deactivate()

    def test_url_field_descriptor(self):
        self._test_field(field_name='url',
                         value_de='http://www.google.de',
                         value_en='http://www.google.com')

    def test_email_field_descriptor(self):
        self._test_field(field_name='email',
                         value_de='django-modeltranslation@googlecode.de',
                         value_en='django-modeltranslation@googlecode.com')


class ModelValidationTest(ModeltranslationTestBase):
    """
    Tests if a translation model field validates correctly.
    """
    def _test_model_validation(self, field_name, invalid_value, valid_value,
                               invalid_value_de):
        """
        Generic model field validation test.
        """
        field_name_en = '%s_en' % field_name
        params = {'title': 'title de', 'title_en': 'title en',
                  field_name: invalid_value}

        has_error_key = False
        # Create an object with an invalid url
        #n = TestModel.objects.create(title='Title', url='foo')
        n = TestModel.objects.create(**params)

        # First check the original field
        # Expect that the validation object contains an error for url
        try:
            n.full_clean()
        except ValidationError, e:
            if field_name in e.message_dict:
                has_error_key = True
        self.assertTrue(has_error_key)

        # Check the translation field
        # Language is set to 'de' at this point
        self.failUnlessEqual(get_language(), 'de')
        # Set translation field to a valid url
        #n.url_de = 'http://code.google.com/p/django-modeltranslation/'
        setattr(n, field_name_en, valid_value)
        has_error_key = False
        # Expect that the validation object contains no error for url
        try:
            n.full_clean()
        except ValidationError, e:
            if field_name_en in e.message_dict:
                has_error_key = True
        self.assertFalse(has_error_key)

        # Set translation field to an invalid url
        #n.url_de = 'foo'
        setattr(n, field_name_en, invalid_value)
        has_error_key = False
        # Expect that the validation object contains an error for url_de
        try:
            n.full_clean()
        except ValidationError, e:
            #if 'url_de' in e.message_dict:
            if field_name_en in e.message_dict:
                has_error_key = True
        self.assertTrue(has_error_key)

    def test_model_validation(self):
        """
        General test for CharField and TextField.
        """
        has_error_key = False
        # Create an object without title (which is required)
        n = TestModel.objects.create(text='Testtext')

        # First check the original field
        # Expect that the validation object contains an error for title
        try:
            n.full_clean()
        except ValidationError, e:
            if 'title' in e.message_dict:
                has_error_key = True
        self.assertTrue(has_error_key)
        n.save()

        # Check the translation field
        # Language is set to 'de' at this point
        self.failUnlessEqual(get_language(), 'de')
        # Set translation field to a valid title
        n.title_de = 'Title'
        has_error_key = False
        # Expect that the validation object contains no error for title
        try:
            n.full_clean()
        except ValidationError, e:
            if 'title_de' in e.message_dict:
                has_error_key = True
        self.assertFalse(has_error_key)

        # Set translation field to an empty title
        n.title_de = None
        has_error_key = False
        # Even though the original field isn't optional, translation fields are
        # per definition always optional. So we expect that the validation
        # object contains no error for title_de.
        try:
            n.full_clean()
        except ValidationError, e:
            if 'title_de' in e.message_dict:
                has_error_key = True
        self.assertFalse(has_error_key)

    def test_model_validation_url_field(self):
        #has_error_key = False
        ## Create an object with an invalid url
        #n = TestModel.objects.create(title='Title', url='foo')

        ## First check the original field
        ## Expect that the validation object contains an error for url
        #try:
            #n.full_clean()
        #except ValidationError, e:
            #if 'url' in e.message_dict:
                #has_error_key = True
        #self.assertTrue(has_error_key)

        ## Check the translation field
        ## Language is set to 'de' at this point
        #self.failUnlessEqual(get_language(), 'de')
        ## Set translation field to a valid url
        #n.url_de = 'http://code.google.com/p/django-modeltranslation/'
        #has_error_key = False
        ## Expect that the validation object contains no error for url
        #try:
            #n.full_clean()
        #except ValidationError, e:
            #if 'url_de' in e.message_dict:
                #has_error_key = True
        #self.assertFalse(has_error_key)

        ## Set translation field to an invalid url
        #n.url_de = 'foo'
        #has_error_key = False
        ## Expect that the validation object contains an error for url_de
        #try:
            #n.full_clean()
        #except ValidationError, e:
            #if 'url_de' in e.message_dict:
                #has_error_key = True
        #self.assertTrue(has_error_key)

        self._test_model_validation(
            field_name='url',
            invalid_value='foo en',
            valid_value='http://code.google.com/p/django-modeltranslation/',
            invalid_value_de='foo de')

    def test_model_validation_email_field(self):
        self._test_model_validation(
            field_name='email', invalid_value='foo en',
            valid_value='django-modeltranslation@googlecode.com',
            invalid_value_de='foo de')


class ModelInheritanceTest(ModeltranslationTestBase):
    """
    Tests for inheritance support in modeltranslation.
    """
    def test_abstract_inheritance(self):
        field_names_b = AbstractModelB._meta.get_all_field_names()
        self.failIf('titled' in field_names_b)
        self.failIf('titled_en' in field_names_b)

    def test_multitable_inheritance(self):
        field_names_a = MultitableModelA._meta.get_all_field_names()
        self.failUnless('titlea' in field_names_a)
        self.failUnless('titlea_en' in field_names_a)

        field_names_b = MultitableModelB._meta.get_all_field_names()
        self.failUnless('titlea' in field_names_b)
        self.failUnless('titlea_en' in field_names_b)
        self.failUnless('titleb' in field_names_b)
        self.failUnless('titleb_en' in field_names_b)

        field_names_c = MultitableModelC._meta.get_all_field_names()
        self.failUnless('titlea' in field_names_c)
        self.failUnless('titlea_en' in field_names_c)
        self.failUnless('titleb' in field_names_c)
        self.failUnless('titleb_en' in field_names_c)
        self.failUnless('titlec' in field_names_c)
        self.failUnless('titlec_en' in field_names_c)

        field_names_d = MultitableModelD._meta.get_all_field_names()
        self.failUnless('titlea' in field_names_d)
        self.failUnless('titlea_en' in field_names_d)
        self.failUnless('titleb' in field_names_d)
        self.failUnless('titleb_en' in field_names_d)
        self.failUnless('titled' in field_names_d)


class TranslationAdminTest(ModeltranslationTestBase):
    def setUp(self):
        trans_real.activate('de')
        self.test_obj = TestModel.objects.create(
            title='Testtitle', text='Testtext')
        self.site = AdminSite()

    def tearDown(self):
        trans_real.deactivate()
        self.test_obj.delete()

    def test_default_fields(self):
        class TestModelAdmin(TranslationAdmin):
            pass

        ma = TestModelAdmin(TestModel, self.site)
        self.assertEqual(
            ma.get_form(request).base_fields.keys(),
            ['title', 'title_en', 'text', 'text_en', 'url', 'url_en',
             'email', 'email_en'])

    def test_default_fieldsets(self):
        class TestModelAdmin(TranslationAdmin):
            pass

        ma = TestModelAdmin(TestModel, self.site)
        # We expect that this behaves the same
        fields = ['title', 'title_en', 'text', 'text_en',
                  'url', 'url_en', 'email', 'email_en']
        self.assertEqual(
            ma.get_fieldsets(request), [(None, {'fields': fields})])
        self.assertEqual(
            ma.get_fieldsets(request, self.test_obj),
            [(None, {'fields': fields})])

    def test_field_arguments(self):
        class TestModelAdmin(TranslationAdmin):
            fields = ['title']

        ma = TestModelAdmin(TestModel, self.site)
        fields = ['title', 'title_en']
        self.assertEqual(ma.get_form(request).base_fields.keys(), fields)
        self.assertEqual(
            ma.get_form(request, self.test_obj).base_fields.keys(), fields)

    def test_field_arguments_restricted_on_form(self):
        # Using `fields`.
        class TestModelAdmin(TranslationAdmin):
            fields = ['title']

        ma = TestModelAdmin(TestModel, self.site)
        fields = ['title', 'title_en']
        self.assertEqual(ma.get_form(request).base_fields.keys(), fields)
        self.assertEqual(
            ma.get_form(request, self.test_obj).base_fields.keys(), fields)

        # Using `fieldsets`.
        class TestModelAdmin(TranslationAdmin):
            fieldsets = [(None, {'fields': ['title']})]

        ma = TestModelAdmin(TestModel, self.site)
        self.assertEqual(ma.get_form(request).base_fields.keys(), fields)
        self.assertEqual(
            ma.get_form(request, self.test_obj).base_fields.keys(), fields)

        # Using `exclude`.
        class TestModelAdmin(TranslationAdmin):
            exclude = ['url', 'email']

        ma = TestModelAdmin(TestModel, self.site)
        fields = ['title', 'title_en', 'text', 'text_en']
        self.assertEqual(
            ma.get_form(request).base_fields.keys(), fields)

        # You can also pass a tuple to `exclude`.
        class TestModelAdmin(TranslationAdmin):
            exclude = ('url', 'email')

        ma = TestModelAdmin(TestModel, self.site)
        self.assertEqual(
            ma.get_form(request).base_fields.keys(), fields)
        self.assertEqual(
            ma.get_form(request, self.test_obj).base_fields.keys(), fields)

        # Using `fields` and `exclude`.
        class TestModelAdmin(TranslationAdmin):
            fields = ['title', 'url']
            exclude = ['url']

        ma = TestModelAdmin(TestModel, self.site)
        self.assertEqual(
            ma.get_form(request).base_fields.keys(), ['title', 'title_en'])

    def test_field_arguments_restricted_on_custom_form(self):
        # Using `fields`.
        class TestModelForm(forms.ModelForm):
            class Meta:
                model = TestModel
                fields = ['url', 'email']

        class TestModelAdmin(TranslationAdmin):
            form = TestModelForm

        ma = TestModelAdmin(TestModel, self.site)
        fields = ['url', 'url_en', 'email', 'email_en']
        self.assertEqual(
            ma.get_form(request).base_fields.keys(), fields)
        self.assertEqual(
            ma.get_form(request, self.test_obj).base_fields.keys(), fields)

        # Using `exclude`.
        class TestModelForm(forms.ModelForm):
            class Meta:
                model = TestModel
                exclude = ['url', 'email']

        class TestModelAdmin(TranslationAdmin):
            form = TestModelForm

        ma = TestModelAdmin(TestModel, self.site)
        fields = ['title', 'title_en', 'text', 'text_en']
        self.assertEqual(
            ma.get_form(request).base_fields.keys(), fields)
        self.assertEqual(
            ma.get_form(request, self.test_obj).base_fields.keys(), fields)

        # If both, the custom form an the ModelAdmin define an `exclude`
        # option, the ModelAdmin wins. This is Django behaviour.
        class TestModelAdmin(TranslationAdmin):
            form = TestModelForm
            exclude = ['url']

        ma = TestModelAdmin(TestModel, self.site)
        fields = ['title', 'title_en', 'text', 'text_en', 'email', 'email_en']
        self.assertEqual(
            ma.get_form(request).base_fields.keys(), fields)
        self.assertEqual(
            ma.get_form(request, self.test_obj).base_fields.keys(), fields)

        # Same for `fields`.
        class TestModelForm(forms.ModelForm):
            class Meta:
                model = TestModel
                fields = ['text', 'title']

        class TestModelAdmin(TranslationAdmin):
            form = TestModelForm
            fields = ['email']

        ma = TestModelAdmin(TestModel, self.site)
        fields = ['email', 'email_en']
        self.assertEqual(
            ma.get_form(request).base_fields.keys(), fields)
        self.assertEqual(
            ma.get_form(request, self.test_obj).base_fields.keys(), fields)

    def test_inline_fieldsets(self):
        class DataInline(TranslationStackedInline):
            model = DataModel
            fieldsets = [
                ('Test', {'fields': ('data',)})
            ]

        class TestModelAdmin(TranslationAdmin):
            exclude = ('title', 'text',)
            inlines = [DataInline]

        class DataTranslationOptions(translator.TranslationOptions):
            fields = ('data',)

        translator.translator.register(DataModel,
                                       DataTranslationOptions)
        ma = TestModelAdmin(TestModel, self.site)

        fieldsets = [('Test', {'fields': ['data', 'data_en']})]

        try:
            ma_fieldsets = ma.get_inline_instances(
                request)[0].get_fieldsets(request)
        except AttributeError:  # Django 1.3 fallback
            ma_fieldsets = ma.inlines[0](
                TestModel, self.site).get_fieldsets(request)
        self.assertEqual(ma_fieldsets, fieldsets)

        try:
            ma_fieldsets = ma.get_inline_instances(
                request)[0].get_fieldsets(request, self.test_obj)
        except AttributeError:  # Django 1.3 fallback
            ma_fieldsets = ma.inlines[0](
                TestModel, self.site).get_fieldsets(request, self.test_obj)
        self.assertEqual(ma_fieldsets, fieldsets)


class MultilingualManagerTest(ModeltranslationTestBase):
    def test_filter(self):
        """
        Test if filtering and updating is language-aware.
        """
        self.assertEqual(True, mt_settings.USE_MULTILINGUAL_MANAGER)

        # Current language is the default language
        self.assertEqual(get_language(), 'de')
        self.assertEqual(mt_settings.DEFAULT_LANGUAGE, 'de')

        n = TestModel.objects.create(title='')
        n.title = 'de'
        n.title_en = 'en'
        n.save()

        m = TestModel.objects.create(title='')
        m.title = 'de'
        m.title_en = 'title en'
        m.save()

        self.assertEqual(TestModel.objects.filter(title='de').count(), 2)
        self.assertEqual(TestModel.objects.filter(title='en').count(), 0)
        self.assertEqual(
            TestModel.objects.filter(title__contains='en').count(), 0)

        # Now switch current language to english
        trans_real.activate('en')
        self.assertEqual(get_language(), 'en')
        self.assertNotEqual(get_language(), mt_settings.DEFAULT_LANGUAGE)

        self.assertEqual(TestModel.objects.filter(title='de').count(), 0)
        self.assertEqual(TestModel.objects.filter(title='en').count(), 1)
        self.assertEqual(
            TestModel.objects.filter(title__contains='en').count(), 2)
        self.assertEqual(
            TestModel.objects.filter(title__startswith='t').count(), 1)

        # Still possible to use explicit language version
        self.assertEqual(
            TestModel.objects.filter(title_en='en').count(), 1)
        self.assertEqual(
            TestModel.objects.filter(title_en__contains='en').count(), 2)

        n.delete()
        m.delete()

    def test_update(self):
#        self.assertEqual(mt_settings.USE_MULTILINGUAL_MANAGER, True)

        # Current language is the default language
        self.assertEqual(get_language(), 'de')
        self.assertEqual(mt_settings.DEFAULT_LANGUAGE, 'de')
        n = TestModel.objects.create(title='')
        n.title = 'de'
        n.title_en = 'en'
        n.save()
        n = TestModel.objects.get(pk=n.pk)
        self.assertEqual(n.title, 'de')
        self.assertEqual(n.__dict__['title'], 'de')
        self.assertEqual(n.title_en, 'en')

        TestModel.objects.update(title='new')
        n = TestModel.objects.get(pk=n.pk)
        self.assertEqual(n.title, 'new')
        self.assertEqual(n.__dict__['title'], 'new')
        self.assertEqual(n.title_en, 'en')

        # Switch to non-default language
        trans_real.activate('en')
        n = TestModel.objects.create(title='')
        n.title = 'de'
        n.title_en = 'en'
        n.save()
        self.assertEqual(n.title, 'en')
        self.assertEqual(n.__dict__['title'], 'de')
        self.assertEqual(n.title_en, 'en')
        n = TestModel.objects.get(pk=n.pk)
        self.assertEqual(n.title, 'en')
        #self.assertEqual(n.__dict__['title'], 'de')
        self.assertEqual(n.title_en, 'en')

        TestModel.objects.update(title='new')
        n = TestModel.objects.get(pk=n.pk)
        self.assertEqual(n.title, 'en')
        self.assertEqual(n.__dict__['title'], 'new')
        self.assertEqual(n.title_en, 'en')

        n.delete()

    def test_q(self):
        """
        Test if Q queries are rewritten.
        """
        n = TestModel.objects.create(title='')
        n.title = 'de'
        n.title_en = 'en'
        n.save()

        self.assertEqual(get_language(), 'de')
        self.assertEqual(
            TestModel.objects.filter(Q(title='de') | Q(pk=42)).count(), 1)
        self.assertEqual(
            TestModel.objects.filter(Q(title='en') | Q(pk=42)).count(), 0)

        trans_real.activate('en')
        self.assertEqual(
            TestModel.objects.filter(Q(title='de') | Q(pk=42)).count(), 0)
        self.assertEqual(
            TestModel.objects.filter(Q(title='en') | Q(pk=42)).count(), 1)

        n.delete()

    def test_f(self):
        """
        Test if F queries **aren't** rewritten.
        """
        self.assertEqual(get_language(), 'de')
        TestModel.objects.create(title_en=1, title=2)

        # Adding strings doesn't work - we will add string numbers instead.
        # Although it is silly, it seems to works (sqlite, MySQL)
        TestModel.objects.update(title=F('title') + 10)
        n = TestModel.objects.all()[0]
        self.assertEqual(n.title, '12')
        self.assertEqual(n.title_en, '1')

        n = TestModel.objects.filter(title__gt=F('title_en') + 10)
        self.assertEqual(len(n), 1)
        n = TestModel.objects.filter(title_en__lt=F('title') + 1)
        self.assertEqual(len(n), 1)

        trans_real.activate('en')
        TestModel.objects.update(title=F('title') + 20)
        n = TestModel.objects.all()[0]
        self.assertEqual(n.title, '1')
        self.assertEqual(n.title_en, '1')

        n = TestModel.objects.filter(title__gt=F('title_en') + 10)
        self.assertEqual(len(n), 0)
        n = TestModel.objects.filter(title_en__lt=F('title') + 1)
        self.assertEqual(len(n), 1)

        n.delete()

    def test_custom_manager(self):
        """
        Test if user-defined manager is still working.
        """
        self.assertEqual(mt_settings.USE_MULTILINGUAL_MANAGER, True)

        n = CustomManagerModel.objects.create(name='')
        n.name = 'foo'
        n.name_en = 'enigma'
        n.save()

        m = CustomManagerModel.objects.create(name='')
        m.name = 'bar'
        m.name_en = 'enigma'
        m.save()

        self.assertEqual(get_language(), 'de')

        # Test presence of custom manager method
        self.assertEqual(CustomManagerModel.objects.foo(), 'bar')

        # Ensure that get_query_set is working
        # Uses filter(name__contains='a')
        self.assertEqual(CustomManagerModel.objects.count(), 1)

        trans_real.activate('en')
        self.assertEqual(CustomManagerModel.objects.count(), 2)

    def test_create(self):
        """
        """
        #self.assertEqual(mt_settings.AUTO_POPULATE, False)
        self.assertEqual(mt_settings.USE_MULTILINGUAL_MANAGER, True)

        trans_real.activate('en')
        n = TestModel.objects.create(title='foo')
        #print '---------'
        #print 'test n.title: %s' % n.title
        #print "test n.__dict__['title']: %s" % n.__dict__['title']
        #print "test n.__dict__['title_en']: %s" % n.__dict__['title_en']
        self.assertEqual(n.title, 'foo')
        self.assertEqual(n.title_en, None)
        self.assertEqual(n.__dict__['title'], 'foo')
        self.assertEqual(n.__dict__['title_en'], None)
        n = TestModel.objects.create(title_en='foo')
        self.assertEqual(n.title, 'foo')
        self.assertEqual(n.title_en, 'foo')
        self.assertEqual(n.__dict__['title'], '')
        self.assertEqual(n.__dict__['title_en'], 'foo')

        trans_real.activate('de')
        n = TestModel.objects.create(title='foo')
        self.assertEqual(n.title, 'foo')
        self.assertEqual(n.title_en, None)
        self.assertEqual(n.__dict__['title'], 'foo')
        self.assertEqual(n.__dict__['title_en'], None)
        n = TestModel.objects.create(title_en='foo')
        self.assertEqual(n.title, '')
        self.assertEqual(n.title_en, 'foo')
        self.assertEqual(n.__dict__['title'], '')
        self.assertEqual(n.__dict__['title_en'], 'foo')

    def test_language_manager(self):
        """
        """
        self.assertEqual(mt_settings.USE_MULTILINGUAL_MANAGER, True)

        TestModel.objects.create(title='de n')
        TestModel.objects.create(title='de m', title_en='en m')
        TestModel.objects.create(title_en='en o')
        qs = TestModel.objects.all()
        self.assertEqual(len(qs), 3)

        trans_real.activate('en')
        TestModel.objects.language()

#    def test_create_populate(self):
#        """
#        Test if language fields are populated with default value on creation.
#        TODO: Do the actual merge.
#        """
#        trans_real.activate('en')
#        self.assertEqual(mt_settings.AUTO_POPULATE, False)
#        self.assertEqual(mt_settings.USE_MULTILINGUAL_MANAGER, True)
#
#        # First check the default behaviour ...
#        n = TestModel.objects.create(title='foo')
#        self.assertEqual(n.title_en, 'foo')
#        self.assertEqual(n.title, None)
#        # .. this is equal to
#        n = TestModel.objects.create(title='foo', _populate=False)
#        self.assertEqual(n.title_en, 'foo')
#        self.assertEqual(n.title, None)
#
#        # Now populate
#        n = TestModel.objects.create(title='foo', _populate=True)
#        self.assertEqual(n.title_en, 'foo')
#        self.assertEqual(n.title, 'foo')
#
#        # You can specify some language...
#        n = TestModel.objects.create(title='foo', title_en='bar',
#                                     _populate=True)
#        self.assertEqual(n.title_en, 'bar')
#        self.assertEqual(n.title, 'foo')
#
#        # ... and remember that still bare attribute points to current
#        # language
#        n = TestModel.objects.create(title='foo', title_en='bar',
#                                     _populate=True)
#        self.assertEqual(n.title_en, 'bar')
#        self.assertEqual(n.title, 'bar')
#
#        trans_real.activate('de')
#        self.assertEqual(n.title, 'foo')
#
#        # This feature (for backward-compatibility) require _populate keyword.
#        n = TestModel.objects.create(title='foo')
#        self.assertEqual(n.title_en, None)
#        self.assertEqual(n.title, 'foo')
#
#        # ... or MODELTRANSLATION_AUTO_POPULATE setting
#        mt_settings.AUTO_POPULATE = True
#        n = TestModel.objects.create(title='foo')
#        self.assertEqual(n.title_en, 'foo')
#        self.assertEqual(n.title, 'foo')
#
#        # _populate keyword has highest priority
#        n = TestModel.objects.create(title='foo', _populate=False)
#        self.assertEqual(n.title_en, None)
#        self.assertEqual(n.title, 'foo')
