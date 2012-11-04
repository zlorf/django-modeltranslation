# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy


class TestModel(models.Model):
    title = models.CharField(ugettext_lazy('title'), max_length=255)
    text = models.TextField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __unicode__(self):
        return self.title


class FallbackTestModel(models.Model):
    title = models.CharField(ugettext_lazy('title'), max_length=255)
    text = models.TextField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)


class FallbackTestModel2(models.Model):
    title = models.CharField(ugettext_lazy('title'), max_length=255)
    text = models.TextField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)


class FileFieldsModel(models.Model):
    title = models.CharField(ugettext_lazy('title'), max_length=255)
    file = models.FileField(upload_to='test', null=True, blank=True)
    file2 = models.FileField(upload_to='test', null=True, blank=True)
    image = models.ImageField(upload_to='test', null=True, blank=True)


class MultitableModelA(models.Model):
    titlea = models.CharField(ugettext_lazy('title a'), max_length=255)


class MultitableModelB(MultitableModelA):
    titleb = models.CharField(ugettext_lazy('title b'), max_length=255)


class MultitableModelC(MultitableModelB):
    titlec = models.CharField(ugettext_lazy('title c'), max_length=255)


class MultitableModelD(MultitableModelB):
    titled = models.CharField(ugettext_lazy('title d'), max_length=255)


class AbstractModelA(models.Model):
    titlea = models.CharField(ugettext_lazy('title a'), max_length=255)

    class Meta:
        abstract = True


class AbstractModelB(AbstractModelA):
    titleb = models.CharField(ugettext_lazy('title b'), max_length=255)


class DataModel(models.Model):
    data = models.TextField(blank=True, null=True)


class CustomManager(models.Manager):
    def get_query_set(self):
        return super(CustomManager, self).get_query_set().filter(
            name__contains='a')

    def foo(self):
        return 'bar'


class CustomManagerModel(models.Model):
    name = models.CharField(max_length=50)

    objects = CustomManager()
