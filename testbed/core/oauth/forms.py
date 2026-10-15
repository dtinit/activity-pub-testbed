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
                'readonly': 'readonly',
                'data-copy': ''
            }),
            'client_secret': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Client Secret',
                'readonly': 'readonly',
                'data-copy': ''
            }),
            'redirect_uris': forms.TextInput(attrs={
                'class': 'form-control', 
                # https is valid in every environment; production and staging reject http.
                'placeholder': 'https://your-service.example/callback'
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

        for uri in uris.split():
            # urlparse lowercases the scheme, so HTTPS:// is accepted as https.
            if urlparse(uri).scheme not in self.allowed_schemes:
                raise forms.ValidationError(
                    f"Each URL must start with {self.allowed_prefixes}"
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
        
        # The accepted schemes are per environment (https only on staging and production)
        # The hint under the field and the validation error both name exactly what this server accepts
        self.allowed_schemes = [s.lower() for s in oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES]
        # e.g. "https://" or "http:// or https://"
        self.allowed_prefixes = " or ".join(f"{scheme}://" for scheme in self.allowed_schemes)
        self.fields['redirect_uris'].help_text = (
            f"Must start with {self.allowed_prefixes}. Separate several URLs with spaces."
        )
        
        self.fields['client_secret'].help_text = (
            "Shown only to you. A destination sends it with your Client id when it exchanges a code for a token."
        )

        client_secret = getattr(self.instance, 'raw_client_secret', None)
        self.initial['client_secret'] = client_secret or ''
        if not client_secret:
            self.fields['client_secret'].widget.attrs['placeholder'] = 'Not available for this account'
