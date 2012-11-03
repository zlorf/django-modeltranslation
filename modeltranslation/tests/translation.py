# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy

from modeltranslation.translator import translator, TranslationOptions
from modeltranslation.tests.models import (
    TestModel, FallbackTestModel, FallbackTestModel2,
    FileFieldsModel, AbstractModelA, AbstractModelB,
    MultitableModelA, MultitableModelB, MultitableModelC,
    CustomManagerModel)


class TestTranslationOptions(TranslationOptions):
    fields = ('title', 'text', 'url', 'email',)
translator.register(TestModel, TestTranslationOptions)


class FallbackTranslationOptions(TranslationOptions):
    fields = ('title', 'text', 'url', 'email',)
    fallback_values = ""
translator.register(FallbackTestModel, FallbackTranslationOptions)


class FallbackTranslationOptions2(TranslationOptions):
    fields = ('title', 'text', 'url', 'email',)
    fallback_values = {
        'text': ugettext_lazy('Sorry, translation is not available.')
    }
translator.register(FallbackTestModel2, FallbackTranslationOptions2)


class FileFieldsModelTranslationOptions(TranslationOptions):
    fields = ('title', 'file', 'image')
translator.register(FileFieldsModel, FileFieldsModelTranslationOptions)


class MultitableModelTranslationOptionsA(TranslationOptions):
    fields = ('titlea',)
translator.register(MultitableModelA, MultitableModelTranslationOptionsA)


class MultitableModelTranslationOptionsB(TranslationOptions):
    fields = ('titleb',)
translator.register(MultitableModelB, MultitableModelTranslationOptionsB)


class MultitableModelTranslationOptionsC(TranslationOptions):
    fields = ('titlec',)
translator.register(MultitableModelC, MultitableModelTranslationOptionsC)


class AbstractModelTranslationOptionsA(TranslationOptions):
    fields = ('titlea',)
translator.register(AbstractModelA, AbstractModelTranslationOptionsA)


class AbstractModelTranslationOptionsB(TranslationOptions):
    fields = ('titleb',)
translator.register(AbstractModelB, AbstractModelTranslationOptionsB)


class CustomManagerModelTranslationOptions(TranslationOptions):
    fields = ('name',)
translator.register(CustomManagerModel, CustomManagerModelTranslationOptions)
