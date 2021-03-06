# Generated by Django 3.0.4 on 2020-09-02 13:52

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academy', '0003_auto_20200831_2336'),
        ('tutors', '0012_wishlist_tut'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invitaions_by_academy',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accepted', models.BooleanField(default=False)),
                ('rejected', models.BooleanField(default=False)),
                ('invitation_sent', models.BooleanField(default=False)),
                ('inivitaion_by_academy', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='academy.Academy')),
                ('tutor_ad', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='tutors.PostAnAd')),
            ],
        ),
    ]
