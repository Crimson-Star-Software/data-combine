from django import forms
from django.forms.fields import CharField, TextInput
from django.forms import ModelForm, inlineformset_factory
from datacombine import models


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


# ContactAddressFormSet = inlineformset_factory(
#     models.Contact,
#     models.Contact.addresses.through,
#     AddressForm,
#     extra=1
# )
