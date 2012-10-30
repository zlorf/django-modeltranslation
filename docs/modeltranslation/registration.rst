.. _registration:

Registering Models for Translation
==================================

The ``modeltranslation`` app can translate ``CharField`` and ``TextField``
based fields (as well as ``FileField`` and ``ImageField`` as of version 0.4)
of any model class. For each model to translate a translation option class
containing the fields to translate is registered with the modeltranslation app.

Registering models and their fields for translation requires the following
steps:

1. Create a ``translation.py`` in your app directory.
2. Create a translation option class for every model to translate.
3. Register the model and the translation option class at the
   ``modeltranslation.translator.translator``

The modeltranslation application reads the ``translation.py`` file in your
app directory thereby triggering the registration of the translation
options found in the file.

A translation option is a class that declares which fields of a model to
translate. The class must derive from ``modeltranslation.ModelTranslation``
and it must provide a ``fields`` attribute storing the list of fieldnames. The
option class must be registered with the
``modeltranslation.translator.translator`` instance.

To illustrate this let's have a look at a simple example using a ``News``
model. The news in this example only contains a ``title`` and a ``text`` field.
Instead of a news, this could be any Django model class:

.. code-block:: python

    class News(models.Model):
        title = models.CharField(max_length=255)
        text = models.TextField()

In order to tell the modeltranslation app to translate the ``title`` and
``text`` field, create a ``translation.py`` file in your news app directory and
add the following:

.. code-block:: python

    from modeltranslation.translator import translator, TranslationOptions
    from news.models import News

    class NewsTranslationOptions(TranslationOptions):
        fields = ('title', 'text',)

    translator.register(News, NewsTranslationOptions)

Note that this does not require to change the ``News`` model in any way, it's
only imported. The ``NewsTranslationOptions`` derives from
``TranslationOptions`` and provides the ``fields`` attribute. Finally the model
and its translation options are registered at the ``translator`` object.

At this point you are mostly done and the model classes registered for
translation will have been added some auto-magical fields. The next section
explains how things are working under the hood.


Changes Automatically Applied to the Model Class
------------------------------------------------

After registering the ``News`` model for translation a SQL dump of the
news app will look like this:

.. code-block:: console

    $ ./manage.py sqlall news
    BEGIN;
    CREATE TABLE `news_news` (
        `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
        `title` varchar(255) NOT NULL,
        `title_en` varchar(255) NULL,
        `text` longtext NULL,
        `text_en` longtext NULL,
    )
    ;
    COMMIT;

Note the ``title_en`` and ``text_en`` fields which are not declared in the
original ``News`` model class but rather have been added by the
modeltranslation app. These are called *translation fields*. There will be
one for every language in your project's ``settings.py`` that is not the
*default language*.

The name of these additional fields is build using the original name of the
translated field and appending one of the language identifiers found in the
``settings.LANGUAGES``.

.. note::
    The first language is treated as the *default language* unless
    modeltranslation is configured to override it (see
    :ref:`settings-default_language`).

As these fields are added to the registered model class as fully valid Django
model fields, they will appear in the db schema for the model although it has
not been specified on the model explicitly.

If you are starting a fresh project and have considered your translation needs
in the beginning then simply sync your database and you are ready to use
the translated models.

In case you are translating an existing project and your models have already
been synced to the database you will need to alter the tables in your database
and add these additional translation fields. Note that all added fields are
declared ``null=True`` no matter if the original field is required. In other
words - all translations are optional.

A management command is provided to handle the addition of new fields. See
:ref:`commands-sync_translation_fields` section for more infos on this.
