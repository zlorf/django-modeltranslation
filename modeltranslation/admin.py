# -*- coding: utf-8 -*-
from copy import deepcopy

from django.contrib import admin
from django.contrib.admin.options import BaseModelAdmin, InlineModelAdmin
from django.contrib.contenttypes import generic

from modeltranslation.settings import DEFAULT_LANGUAGE
from modeltranslation.translator import translator
from modeltranslation.utils import (build_localized_fieldname,
                                    build_css_class)


class TranslationBaseModelAdmin(BaseModelAdmin):
    _original_css_classes = {}

    def __init__(self, *args, **kwargs):
        super(TranslationBaseModelAdmin, self).__init__(*args, **kwargs)
        self.trans_opts = translator.get_options_for_model(self.model)

    def formfield_for_dbfield(self, db_field, **kwargs):
        field = super(TranslationBaseModelAdmin, self).formfield_for_dbfield(
            db_field, **kwargs)
        self.patch_translation_field(db_field, field, **kwargs)
        return field

    def add_css_classes(self, db_field, field):
        """
        Adds modeltranslation css classes to identify a modeltranslation widget
        and make it easier to use in frontend code.
        """
        if (db_field.name in self.trans_opts.localized_fieldnames_rev or
            db_field.name in self.trans_opts.fields):
            css_classes = field.widget.attrs.get('class', '').split(' ')
            css_classes.append('mt')
            if db_field.name in self.trans_opts.localized_fieldnames_rev:
                css_classes.append(
                    build_css_class(db_field.name, 'mt-field'))
            elif db_field.name in self.trans_opts.fields:
                css_classes.append(
                    build_css_class(build_localized_fieldname(
                        db_field.name, DEFAULT_LANGUAGE), 'mt-field'))
                # Add another css class to identify the original field
                css_classes.append('mt-original-field')
            field.widget.attrs['class'] = ' '.join(css_classes)

    def get_widget(self, orig_formfield):
        # Return a deepcopy of the original field widget
        return deepcopy(orig_formfield.widget)

    def patch_translation_field(self, db_field, field, **kwargs):
        if db_field.name in self.trans_opts.localized_fieldnames_rev:
            orig_fieldname = self.trans_opts.localized_fieldnames_rev[
                db_field.name]
            orig_formfield = self.formfield_for_dbfield(
                self.model._meta.get_field(orig_fieldname), **kwargs)
            # Store original field css classes as they would be wiped out
            # by the widget deepcopy.
            self._original_css_classes[
                orig_fieldname] = field.widget.attrs.get('class', '')
            # For every localized field copy the widget from the original field
            field.widget = self.get_widget(orig_formfield)
            # Restore original field css classes
            field.widget.attrs['class'] = self._original_css_classes[
                orig_fieldname]
        self.add_css_classes(db_field, field)


class TranslationAdmin(TranslationBaseModelAdmin, admin.ModelAdmin):
    pass


class TranslationInlineModelAdmin(TranslationBaseModelAdmin, InlineModelAdmin):
    pass


class TranslationTabularInline(TranslationInlineModelAdmin,
                               admin.TabularInline):
    pass


class TranslationStackedInline(TranslationInlineModelAdmin,
                               admin.StackedInline):
    pass


class TranslationGenericTabularInline(TranslationInlineModelAdmin,
                                      generic.GenericTabularInline):
    pass


class TranslationGenericStackedInline(TranslationInlineModelAdmin,
                                      generic.GenericStackedInline):
    pass
