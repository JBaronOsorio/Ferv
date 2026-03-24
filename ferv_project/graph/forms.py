from django import forms


class PreferenceQuestionnaireForm(forms.Form):
    PLACE_TYPE_CHOICES = [
        ('bars', 'Bars'),
        ('cafes', 'Cafes'),
        ('restaurants', 'Restaurants'),
        ('parks', 'Parks'),
        ('galleries', 'Galleries'),
    ]
    AMBIENCE_CHOICES = [
        ('quiet', 'Quiet'),
        ('lively', 'Lively'),
        ('intimate', 'Intimate'),
        ('family_friendly', 'Family Friendly'),
    ]
    ACTIVITY_CHOICES = [
        ('live_music', 'Live Music'),
        ('reading', 'Reading'),
        ('socializing', 'Socializing'),
        ('outdoor_walks', 'Outdoor Walks'),
        ('art_exhibitions', 'Art Exhibitions'),
    ]
    BUDGET_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('premium', 'Premium'),
    ]

    place_types = forms.MultipleChoiceField(
        choices=PLACE_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    ambiences = forms.MultipleChoiceField(
        choices=AMBIENCE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    activities = forms.MultipleChoiceField(
        choices=ACTIVITY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    budget_range = forms.ChoiceField(choices=BUDGET_CHOICES, required=True)
