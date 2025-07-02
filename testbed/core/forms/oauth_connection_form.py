from django import forms
from oauth2_provider.models import get_application_model

Application = get_application_model()

class OAuthApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['name', 'client_id', 'client_secret', 'redirect_uris']
        labels = {
            'name': 'Service Name',
            'redirect_uris': 'Redirect URL'
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'My ActivityPub Service'
            }),
            'client_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Client ID'}),
            'client_secret': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Client Secret'}),
            'redirect_uris': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter a valid URL (e.g., http://localhost:8000/callback)'
            }),
        }
    
    # Ensure redirect URIs are properly formatted
    def clean_redirect_uris(self):
        uris = self.cleaned_data.get('redirect_uris', '')
        if not uris:
            raise forms.ValidationError("Redirect URL is required")
        
        # Simple validation - could be expanded for more strict checks
        for uri in uris.split():
            if not uri.startswith(('http://', 'https://')):
                raise forms.ValidationError(
                    "Each URI must start with http:// or https://"
                )
        
        return uris
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default values for required fields that users don't need to see for now
        if not self.instance.pk:
            
            self.instance.client_type = 'confidential'
            self.instance.authorization_grant_type = 'authorization-code'
        
        self.fields['redirect_uris'].help_text = ''
