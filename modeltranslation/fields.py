# -*- coding: utf-8 -*-
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import File
from django.db.models.fields import CharField, TextField
from django.db.models.fields.files import (FileField, FieldFile, ImageField,
                                           ImageFileDescriptor, FileDescriptor)

from modeltranslation import settings as mt_settings
from modeltranslation.utils import (get_language, build_localized_fieldname,
                                    build_localized_verbose_name)


SUPPORTED_FIELDS = (CharField, TextField, FileField, ImageField,)


def create_translation_field(model, field_name, lang):
    """
    Translation field factory. Returns a ``TranslationField`` based on a
    fieldname and a language.

    The list of supported fields can be extended by defining a tuple of field
    names in the projects settings.py like this::

        MODELTRANSLATION_CUSTOM_FIELDS = ('MyField', 'MyOtherField',)

    If the class is neither a subclass of fields in ``SUPPORTED_FIELDS``, nor
    in ``CUSTOM_FIELDS`` an ``ImproperlyConfigured`` exception will be raised.
    """
    field = model._meta.get_field(field_name)
    cls_name = field.__class__.__name__
    if not (isinstance(field, SUPPORTED_FIELDS) or
            cls_name in mt_settings.CUSTOM_FIELDS):
        raise ImproperlyConfigured(
            '%s is not supported by modeltranslation.' % cls_name)
    translation_cls = field_factory(field.__class__)
    return translation_cls(translated_field=field, language=lang)


def field_factory(baseclass):
    class TranslationField(TranslationFieldBase, baseclass):
        pass
    return TranslationField


class TranslationFieldBase(object):
    """
    The translation field functions as a proxy to the original field which is
    wrapped.

    For every field defined in the model's ``TranslationOptions`` localized
    versions of that field are added to the model depending on the languages
    given in ``settings.LANGUAGES``.

    If for example there is a model ``News`` with a field ``title`` which is
    registered for translation and the ``settings.LANGUAGES`` contains the
    ``de`` and ``en`` languages, the fields ``title_de`` and ``title_en`` will
    be added to the model class. These fields are realized using this
    descriptor.

    The translation field needs to know which language it contains therefore
    that needs to be specified when the field is created.
    """
    def __init__(self, translated_field, language, *args, **kwargs):
        # Update the dict of this field with the content of the original one
        # This might be a bit radical?! Seems to work though...
        self.__dict__.update(translated_field.__dict__)
        self._post_init(translated_field, language)

    def _post_init(self, translated_field, language):
        """
        Common init for subclasses of TranslationFieldBase.
        """
        # Store the originally wrapped field for later
        self.translated_field = translated_field
        self.language = language

        # Translation are always optional (for now - maybe add some parameters
        # to the translation options for configuring this)
        self.null = True
        self.blank = True

        # Adjust the name of this field to reflect the language
        self.attname = build_localized_fieldname(
            self.translated_field.name, self.language)
        self.name = self.attname

        # Copy the verbose name and append a language suffix
        # (will show up e.g. in the admin).
        self.verbose_name = build_localized_verbose_name(
            translated_field.verbose_name, language)

    def get_prep_value(self, value):
        if value == '':
            value = None
        return self.translated_field.get_prep_value(value)

    def get_prep_lookup(self, lookup_type, value):
        return self.translated_field.get_prep_lookup(lookup_type, value)

    def to_python(self, value):
        return self.translated_field.to_python(value)

    def get_internal_type(self):
        return self.translated_field.get_internal_type()

    def south_field_triple(self):
        """
        Returns a suitable description of this field for South.
        """
        # We'll just introspect the _actual_ field.
        from south.modelsinspector import introspector
        field_class = '%s.%s' % (self.translated_field.__class__.__module__,
                                 self.translated_field.__class__.__name__)
        args, kwargs = introspector(self)
        # That's our definition!
        return (field_class, args, kwargs)

    def formfield(self, *args, **kwargs):
        """
        Preserves the widget of the translated field.
        """
        trans_formfield = self.translated_field.formfield(*args, **kwargs)
        defaults = {'widget': type(trans_formfield.widget)}
        defaults.update(kwargs)
        return super(TranslationFieldBase, self).formfield(*args, **defaults)


class TranslationDescriptor(object):
    """
    A descriptor used for the original field (e.g. ``title``).
    """
    def __init__(self, field, initial_val='', fallback_value=None):
        """
        The ``field`` is the model field the descriptor is applied to.
        """
        self.field = field
        self.val = initial_val
        self.fallback_value = fallback_value

    def __set__(self, instance, value):
        instance.__dict__[self.field.name] = value

    def __get__(self, instance, owner):
        if not instance:
            raise ValueError(
                "Translation field '%s' can only be accessed via an instance "
                "not via a class." % self.field.name)
        lang = get_language()

        # If current language is the default language, simply return the
        # fields standard value.
        if lang == mt_settings.DEFAULT_LANGUAGE:
            #print ('If current language is the default language, simply '
            #       'return the fields standard value (lang: %s).' % lang)
            return instance.__dict__[self.field.name]

        loc_field_name = build_localized_fieldname(self.field.name, lang)
        if hasattr(instance, loc_field_name):
            if getattr(instance, loc_field_name):
                # Return current language's translation field value
                # (e.g. ``title_de``).
                #print 'Return current languages translation field value'
                return getattr(instance, loc_field_name)
            elif self.fallback_value is None:
                # Return standard field value
                #print 'Return standard field value (loc_field_name: %s)' % (
                #    loc_field_name)
                return instance.__dict__[self.field.name]
            else:
                # Return fallback field value
                #print 'Return fallback field value'
                return self.fallback_value


class TranslationFileDescriptor(FileDescriptor):
    """
    The descriptor for the file attribute on the model instance. Returns a
    FieldFile when accessed so you can do stuff like::

        >>> instance.file.size

    Assigns a file object on assignment so you can do::

        >>> instance.file = File(...)

    Essentially a copy of Django's own FileDescriptor modified to be aware of
    the current language.
    """
    def __get__(self, instance=None, owner=None):
        if instance is None:
            raise AttributeError(
                "The '%s' attribute can only be accessed from %s instances."
                % (self.field.name, owner.__name__))

        # This is slightly complicated, so worth an explanation.
        # instance.file`needs to ultimately return some instance of `File`,
        # probably a subclass. Additionally, this returned object needs to have
        # the FieldFile API so that users can easily do things like
        # instance.file.path and have that delegated to the file storage
        # engine.
        # Easy enough if we're strict about assignment in __set__, but if you
        # peek below you can see that we're not. So depending on the current
        # value of the field we have to dynamically construct some sort of
        # "thing" to return.

        lang = get_language()

        # If the current language is not the default language, use the value of
        # the field that maps to the current language.
        if lang == mt_settings.DEFAULT_LANGUAGE:
            field_name = self.field.name
        else:
            field_name = build_localized_fieldname(self.field.name, lang)

        # The instance dict contains whatever was originally assigned
        # in __set__.
        file = instance.__dict__[field_name]

        # If this value is a string (instance.file = "path/to/file") or None
        # then we simply wrap it with the appropriate attribute class according
        # to the file field. [This is FieldFile for FileFields and
        # ImageFieldFile for ImageFields; it's also conceivable that user
        # subclasses might also want to subclass the attribute class]. This
        # object understands how to convert a path to a file, and also how to
        # handle None.
        if isinstance(file, basestring) or file is None:
            attr = self.field.attr_class(instance, self.field, file)
            instance.__dict__[field_name] = attr

        # Other types of files may be assigned as well, but they need to have
        # the FieldFile interface added to the. Thus, we wrap any other type of
        # File inside a FieldFile (well, the field's attr_class, which is
        # usually FieldFile).
        elif isinstance(file, File) and not isinstance(file, FieldFile):
            file_copy = self.field.attr_class(instance, self.field, file.name)
            file_copy.file = file
            file_copy._committed = False
            instance.__dict__[field_name] = file_copy

        # Finally, because of the (some would say boneheaded) way pickle works,
        # the underlying FieldFile might not actually itself have an associated
        # file. So we need to reset the details of the FieldFile in those
        # cases.
        elif isinstance(file, FieldFile) and not hasattr(file, 'field'):
            file.instance = instance
            file.field = self.field
            file.storage = self.field.storage

        # That was fun, wasn't it?
        return instance.__dict__[field_name]


class TranslationImageDescriptor(TranslationFileDescriptor,
                                 ImageFileDescriptor):
    """
    Django's original ``ImageDescriptor`` only overrides ``__set__``, so we
    just inherit here, no additional work required.
    """
    pass
