from django import forms


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
