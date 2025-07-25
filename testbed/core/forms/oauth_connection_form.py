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
            'client_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Client ID',
                'readonly': 'readonly'
            }),
            'client_secret': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Client Secret',
                'readonly': 'readonly'
            }),
            'redirect_uris': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter a valid URL (e.g., http://localhost:8000/callback). Add multiples separated by spaces'
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
        
        if hasattr(self, 'instance') and self.instance and self.instance.authorization_grant_type == 'authorization-code' and not uris:
            raise forms.ValidationError("Redirect URL is required for authorization code grant type")
        
        return uris
    
    # Override save method to prevent updating client_id and client_secret
    def save(self, commit=True):
        instance = super(OAuthApplicationForm, self).save(commit=False)
        
        # If this is an existing instance, preserve the original credentials
        if instance.pk:
            original = Application.objects.get(pk=instance.pk)
            instance.client_id = original.client_id
            instance.client_secret = original.client_secret
            
        if commit:
            instance.save()
        return instance
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default values for required fields that users don't need to see for now
        if not self.instance.pk:
            
            self.instance.client_type = 'confidential'
            self.instance.authorization_grant_type = 'authorization-code'
        
        self.fields['redirect_uris'].help_text = ''
