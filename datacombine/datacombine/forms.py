from django import forms
from django.forms.fields import CharField, TextInput
from django.forms.widgets import Select
from django.forms import ModelForm, inlineformset_factory
from datacombine import models, settings
import re


class CustomOrderingWidget(Select):
    def __init__(self, priority_regex, sort='+', attrs=None):
        super(CustomOrderingWidget, self).__init__(attrs)
        self.regex = re.compile(priority_regex)
        self.sort = sort
        self.template_name = 'django/forms/widgets/select.html'

    def render(self, name, value, attrs=None, renderer=None):
        context = self.get_context(name, value, attrs)
        optgroups = context.get('widget').get('optgroups')
        firsts, others = [], []
        for grp in optgroups:
            if self.regex.search(grp[1][0].get('label')):
                firsts.append(grp)
            else:
                others.append(grp)
        if self.sort == '+':
            kfn = lambda x: x[1][0].get('label')
            context['widget']['optgroups'] = sorted(firsts, key=kfn) +\
                                               sorted(others, key=kfn)
        elif self.sort == '-':
            kfn = lambda x: x[1][0].get('label')
            context['widget']['optgroups'] =\
                sorted(firsts, key=kfn, reverse=True) +\
                sorted(others, key=kfn, reverse=True)
        else:
            context['widget']['optgroups'] = firsts + others
        return self._render(self.template_name, context, renderer)


class HarvestForm(forms.Form):
    json_file = forms.FileField(required=False)
    api_key = forms.CharField(
        required=False,
        max_length=24,
        widget=forms.TextInput(
            attrs=dict(maxlength="200")
        )
    )
    auth_key = forms.CharField(
        required=False,
        max_length=36,
        widget=forms.TextInput(
            attrs=dict(maxlength="200")
        )
    )
    postgres_password = forms.CharField(
        required=False,
        max_length=36,
        widget=forms.TextInput(
            attrs=dict(maxlength="200")
        )
    )

    def clean(self):
        cleaned_data = super().clean()
        json_fname = cleaned_data.get("json_file")
        api_key = cleaned_data.get("api_key")
        auth_key = cleaned_data.get("auth_key")
        postgres_password = cleaned_data.get("postgres_password")
        if not json_fname:
            if not (api_key and auth_key and postgres_password):
                raise forms.ValidationError(
                    "There needs to be either a json file "
                    "or Constant Contact API/postgres credentials."
                )


class AddressForm(ModelForm):
    class Meta:
        model = models.Address
        exclude = ["cc_id"]
        label = {
            'line1': 'Address Line 1',
            'line2': 'Address Line 2',
            'line3': 'Address Line 3'
        }
        fields_required = []


class EmailAddressForm(ModelForm):
    class Meta:
        model = models.EmailAddress
        exclude = ["cc_id"]
        fields_required = ["email_address"]


class CreateContactForm(ModelForm):
    cell_field = CharField(label="Cell Phone")
    home_field = CharField(label="Home Phone")
    work_field = CharField(label="Work Phone")
    fax_field = CharField(label="Fax")
    note = TextInput()

    class Meta:
        model = models.Contact
        exclude = [
            "created_date",
            "cc_id",
            "cc_modified_date",
            "cell_phone",
            "home_phone",
            "work_phone",
            "fax",
            "addresses",
            "email_addresses"
        ]
        fields_required = ["first_name"]

        widgets = {
            'cc_lists': CustomOrderingWidget("^{0}".format(
                settings.PREF_ORGANIZATION_PREFIX
            ))
        }
