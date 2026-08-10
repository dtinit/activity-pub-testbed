from urllib.parse import urlparse

from django import forms
from oauth2_provider.models import get_application_model
from oauth2_provider.settings import oauth2_settings

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
                # https is valid in every environment; production and staging reject http.
                'placeholder': 'Enter a valid URL (e.g., https://your-service.example/callback). Add multiples separated by spaces'
            }),
        }
    
    def clean_redirect_uris(self):
        """
        Validate the redirect URLs registered for this OAuth application.

        Accepted schemes come from OAUTH2_PROVIDER["ALLOWED_REDIRECT_URI_SCHEMES"] which is
        the same setting ActivityPubOAuth2Validator.validate_redirect_uri enforces at
        authorization time, and that django-oauth-toolkit enforces in Application.clean().

        Production and staging allow https only.

        Returns:
            str: the space-separated redirect URIs, unchanged, when every one of
            them uses an allowed scheme.
        """
        uris = self.cleaned_data.get('redirect_uris', '')
        if not uris:
            raise forms.ValidationError("Redirect URL is required")

        allowed_schemes = [s.lower() for s in oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES]
        # Rendered into the error message, e.g. "https://" or "http:// or https://"
        expected_prefixes = " or ".join(f"{scheme}://" for scheme in allowed_schemes)

        for uri in uris.split():
            # urlparse lowercases the scheme, so HTTPS:// is accepted as https.
            if urlparse(uri).scheme not in allowed_schemes:
                raise forms.ValidationError(
                    f"Each URL must start with {expected_prefixes}"
                )
        
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
