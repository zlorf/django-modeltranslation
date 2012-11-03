# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy

from modeltranslation.translator import translator, TranslationOptions
from modeltranslation.tests.models import (
    TestModel, TestModelFallback, TestModelFallback2,
    TestModelFileFields, TestModelAbstractA, TestModelAbstractB,
    TestModelMultitableA, TestModelMultitableB, TestModelMultitableC,
    TestModelCustomManager)


class TestTranslationOptions(TranslationOptions):
    fields = ('title', 'text', 'url', 'email',)
translator.register(TestModel, TestTranslationOptions)


class TestTranslationOptionsFallback(TranslationOptions):
    fields = ('title', 'text', 'url', 'email',)
    fallback_values = ""
translator.register(TestModelFallback,
                    TestTranslationOptionsFallback)


class TestTranslationOptionsFallback2(TranslationOptions):
    fields = ('title', 'text', 'url', 'email',)
    fallback_values = {'text': ugettext_lazy('Sorry, translation is not '
                                             'available.')}
translator.register(TestModelFallback2,
                    TestTranslationOptionsFallback2)


class TestTranslationOptionsModelFileFields(TranslationOptions):
    fields = ('title', 'file', 'image')
translator.register(TestModelFileFields,
                    TestTranslationOptionsModelFileFields)


class TranslationOptionsTestModelMultitableA(TranslationOptions):
    fields = ('titlea',)
translator.register(TestModelMultitableA,
                    TranslationOptionsTestModelMultitableA)


class TranslationOptionsTestModelMultitableB(TranslationOptions):
    fields = ('titleb',)
translator.register(TestModelMultitableB,
                    TranslationOptionsTestModelMultitableB)


class TranslationOptionsTestModelMultitableC(TranslationOptions):
    fields = ('titlec',)
translator.register(TestModelMultitableC,
                    TranslationOptionsTestModelMultitableC)


class TranslationOptionsTestModelAbstractA(TranslationOptions):
    fields = ('titlea',)
translator.register(TestModelAbstractA,
                    TranslationOptionsTestModelAbstractA)


class TranslationOptionsTestModelAbstractB(TranslationOptions):
    fields = ('titleb',)
translator.register(TestModelAbstractB,
                    TranslationOptionsTestModelAbstractB)


class TranslationOptionsTestModelCustomManager(TranslationOptions):
    fields = ('name',)
translator.register(TestModelCustomManager,
                    TranslationOptionsTestModelCustomManager)
