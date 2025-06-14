from django import forms
from testbed.core.models import OauthConnection

class OauthConnectionForm(forms.ModelForm):
    class Meta:
        model = OauthConnection
        fields = ['client_id', 'client_secret', 'redirect_url']
        widgets = {
                    'client_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Client ID'}),
                    'client_secret': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Client Secret'}),
                    'redirect_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Redirect URL'}),
               }