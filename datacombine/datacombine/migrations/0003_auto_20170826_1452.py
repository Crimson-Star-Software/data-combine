# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-08-26 14:52
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('datacombine', '0002_auto_20170826_0303'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='contact',
            name='notes',
        ),
        migrations.AddField(
            model_name='note',
            name='about',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='datacombine.Contact'),
        ),
    ]
