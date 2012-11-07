# -*- coding: utf-8 -*-
from django.conf import settings
from django.db.models.base import ModelBase
from django.db.models.fields.files import ImageFileDescriptor, FileDescriptor
from django.db.models.signals import pre_save, post_save
from django.utils import translation

from modeltranslation import settings as mt_settings
from modeltranslation.fields import (TranslationDescriptor,
                                     TranslationFileDescriptor,
                                     TranslationImageDescriptor,
                                     create_translation_field)
from modeltranslation.utils import build_localized_fieldname, get_language


class AlreadyRegistered(Exception):
    pass


class NotRegistered(Exception):
    pass


class TranslationOptions(object):
    """
    The TranslationOptions object is used to specify the fields to translate.

    The options are registered in combination with a model class at the
    ``modeltranslation.translator.translator`` instance.

    It caches the content type of the translated model for faster lookup later
    on.
    """
    def __init__(self, *args, **kwargs):
        self.localized_fieldnames = []


def add_localized_fields(model):
    """
    Monkey patchs the original model class to provide additional fields for
    every language. Only do that for fields which are defined in the
    translation options of the model.

    Returns a dict mapping the original fieldname to a list containing the
    names of the localized fields created for the original field.
    """
    localized_fields = dict()
    translation_opts = translator.get_options_for_model(model)
    for field_name in translation_opts.fields:
        localized_fields[field_name] = list()
        for l in settings.LANGUAGES:
            # Create a dynamic translation field
            translation_field = create_translation_field(
                model=model, field_name=field_name, lang=l[0])
            # Construct the name for the localized field
            localized_field_name = build_localized_fieldname(field_name, l[0])
            # Check if the model already has a field by that name
            if hasattr(model, localized_field_name):
                raise ValueError(
                    "Error adding translation field. Model '%s' already "
                    "contains a field named '%s'." % (
                        model._meta.object_name, localized_field_name))
            # This approach implements the translation fields as full valid
            # django model fields and therefore adds them via add_to_class
            model.add_to_class(localized_field_name, translation_field)
            localized_fields[field_name].append(localized_field_name)

    return localized_fields


#def translated_model_initialized(field_names, instance, **kwargs):
    #print "translated_model_initialized instance:", \
          #instance, ", field:", field_names
    #for field_name in field_names:
        #initial_val = getattr(instance, field_name)
        #print "  field: %s, initialval: %s" % (field_name, initial_val)
        #setattr(instance.__class__, field_name,
                #TranslationFieldDescriptor(field_name, initial_val))


#def translated_model_initializing(sender, args, kwargs, **signal_kwargs):
    #print "translated_model_initializing", sender, args, kwargs
    #trans_opts = translator.get_options_for_model(sender)
    #for field_name in trans_opts.fields:
        #setattr(sender, field_name, TranslationFieldDescriptor(field_name))


def delete_cache_fields(model):
    opts = model._meta
    try:
        del opts._field_cache
    except AttributeError:
        pass
    try:
        del opts._field_name_cache
    except AttributeError:
        pass
    try:
        del opts._name_map
    except AttributeError:
        pass


class Translator(object):
    """
    A Translator object encapsulates an instance of a translator. Models are
    registered with the Translator using the register() method.
    """
    def __init__(self):
        # model_class class -> translation_opts instance
        self._registry = {}

    def register(self, model_or_iterable, translation_opts, **options):
        """
        Registers the given model(s) with the given translation options.

        The model(s) should be Model classes, not instances.

        If a model is already registered for translation, this will raise
        AlreadyRegistered.
        """
        if isinstance(model_or_iterable, ModelBase):
            model_or_iterable = [model_or_iterable]

        for model in model_or_iterable:
            if model in self._registry:
                raise AlreadyRegistered('The model %s is already registered '
                                        'for translation' % model.__name__)

            pre_save.connect(pre_save_fix_handler, sender=model)
            post_save.connect(post_save_fix_handler, sender=model)

            # If we got **options then dynamically construct a subclass of
            # translation_opts with those **options.
            if options:
                # For reasons I don't quite understand, without a __module__
                # the created class appears to "live" in the wrong place,
                # which causes issues later on.
                options['__module__'] = __name__
                translation_opts = type(
                    "%sTranslationOptions" % model.__name__,
                    (translation_opts,), options)

            # Store the translation class associated to the model
            self._registry[model] = translation_opts

            # Add the localized fields to the model and store the names of
            # these fields in the model's translation options for faster lookup
            # later on.
            translation_opts.localized_fieldnames = add_localized_fields(model)

            # Create a reverse dict mapping the localized_fieldnames to the
            # original fieldname
            rev_dict = dict()
            for orig_name, loc_names in \
                    translation_opts.localized_fieldnames.items():
                for ln in loc_names:
                    rev_dict[ln] = orig_name
            translation_opts.localized_fieldnames_rev = rev_dict

            # Delete all fields cache for related model (parent and children)
            for related_obj in model._meta.get_all_related_objects():
                delete_cache_fields(related_obj.model)

            model_fallback_values = getattr(
                translation_opts, 'fallback_values', None)
            for field_name in translation_opts.fields:
                if model_fallback_values is None:
                    field_fallback_value = None
                elif isinstance(model_fallback_values, dict):
                    field_fallback_value = model_fallback_values.get(
                        field_name, None)
                else:
                    field_fallback_value = model_fallback_values

                # Apply translation field descriptor retaining special
                # descriptors for file and image fields
                field = model._meta.get_field(field_name)
                descriptor_class = getattr(field, 'descriptor_class', None)
                if descriptor_class is FileDescriptor:
                    setattr(model, field_name, TranslationFileDescriptor(
                        field=field))
                elif descriptor_class is ImageFileDescriptor:
                    setattr(model, field_name, TranslationImageDescriptor(
                        field=field))
                else:
                    setattr(model, field_name, TranslationDescriptor(
                        field=field, fallback_value=field_fallback_value))

        #signals.pre_init.connect(translated_model_initializing, sender=model,
                                 #weak=False)

    def unregister(self, model_or_iterable):
        """
        Unregisters the given model(s).

        If a model isn't already registered, this will raise NotRegistered.
        """
        if isinstance(model_or_iterable, ModelBase):
            model_or_iterable = [model_or_iterable]
        for model in model_or_iterable:
            if model not in self._registry:
                raise NotRegistered('The model "%s" is not registered for '
                                    'translation' % model.__name__)
            del self._registry[model]

    def get_options_for_model(self, model):
        """
        Returns the translation options for the given ``model``. If the
        ``model`` is not registered a ``NotRegistered`` exception is raised.
        """
        try:
            return self._registry[model]
        except KeyError:
            # Try to find a localized parent model and build a dedicated
            # translation options class with the parent info.
            # Useful when a ModelB inherits from ModelA and only ModelA fields
            # are localized. No need to register ModelB.
            fields = set()
            localized_fieldnames = {}
            localized_fieldnames_rev = {}
            for parent in model._meta.parents.keys():
                if parent in self._registry:
                    trans_opts = self._registry[parent]
                    fields.update(trans_opts.fields)
                    localized_fieldnames.update(
                        trans_opts.localized_fieldnames)
                    localized_fieldnames_rev.update(
                        trans_opts.localized_fieldnames_rev)
            if fields and localized_fieldnames and localized_fieldnames_rev:
                options = {
                    '__module__': __name__,
                    'fields': tuple(fields),
                    'localized_fieldnames': localized_fieldnames,
                    'localized_fieldnames_rev': localized_fieldnames_rev
                }
                translation_opts = type(
                    "%sTranslation" % model.__name__,
                    (TranslationOptions,), options)
                # delete_cache_fields(model)
                return translation_opts
            raise NotRegistered('The model "%s" is not registered for '
                                'translation' % model.__name__)


def pre_save_fix_handler(sender, **kwargs):
    instance = kwargs['instance']

    # Force default language on save. See issue #33 for details.
    setattr(instance, '_current_lang', get_language())
    translation.activate(mt_settings.DEFAULT_LANGUAGE)

#    if mt_settings.DEFAULT_LANGUAGE == self.language and not add:
#    #if mt_settings.DEFAULT_LANGUAGE == get_language() and not add:
#        # Rule is: 3. Assigning a value to a translation field of the
#        # default language also updates the original field
#        model_instance.__dict__[self.translated_field.attname] = val
#    return val

#    for orig_fieldname in translator.get_options_for_model(
#            sender).localized_fieldnames.keys():
#        if hasattr(instance, orig_fieldname):
#            default_lang_fieldname = build_localized_fieldname(
#                orig_fieldname, mt_settings.DEFAULT_LANGUAGE)
#            if not getattr(instance, default_lang_fieldname):
#                field = sender._meta.get_field(orig_fieldname)
#                if field.null:
#                    setattr(instance, orig_fieldname, None)
#                else:
#                    setattr(instance, orig_fieldname, '')


def post_save_fix_handler(sender, **kwargs):
    instance = kwargs['instance']
    translation.activate(instance._current_lang)


# This global object represents the singleton translator object
translator = Translator()
