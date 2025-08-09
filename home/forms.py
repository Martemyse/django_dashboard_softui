from django import forms
from .models import User, ObratiOddelki, UserGroup, UserAppRole
from django.contrib.auth.forms import AuthenticationForm

class DevelopmentAuthenticationForm(AuthenticationForm):
    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

class UserForm(forms.ModelForm):
    username = forms.CharField(
        label="Uporabniško ime", 
        max_length=50,
        widget=forms.TextInput(attrs={'id': 'id_username_add_user', 'class': 'form-control'})
    )
    first_name = forms.CharField(
        label="Ime", 
        max_length=255,
        widget=forms.TextInput(attrs={'id': 'id_first_name_add_user', 'class': 'form-control'})
    )
    last_name = forms.CharField(
        label="Priimek", 
        max_length=255,
        widget=forms.TextInput(attrs={'id': 'id_last_name_add_user', 'class': 'form-control'})
    )
    email = forms.EmailField(
        label="LTH E-poštni naslov", 
        max_length=255,
        widget=forms.EmailInput(attrs={'id': 'id_email_add_user', 'class': 'form-control'})
    )
    user_role = forms.ChoiceField(
        label="Tip računa",
        choices=[('osnovni', 'osnovni'), ('vodja', 'vodja'), ('admin', 'admin')],
        widget=forms.Select(attrs={'id': 'id_user_role_add_user', 'class': 'form-control'})
    )
    is_active = forms.BooleanField(
        label="Aktiven", 
        required=False, 
        initial=True
    )
    is_rezija = forms.BooleanField(  # New field for 'is_rezija'
        label="Režija", 
        required=False, 
        initial=False
    )
    obrat_oddelek = forms.ModelChoiceField(
        label="Obrat in Oddelek",
        queryset=ObratiOddelki.objects.none(),
        to_field_name='obrati_oddelki_id',
        widget=forms.Select(attrs={'id': 'id_obrat_oddelek_add_user', 'class': 'form-control'}),
        empty_label="--- Izberite obrat in oddelek ---"
    )

    groups = forms.ModelMultipleChoiceField(
        queryset=UserGroup.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'id': 'id_groups_add_user'}),
        required=False,
        label="Skupine"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'user_role', 'obrat_oddelek', 'groups', 'is_active', 'is_rezija']

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super(UserForm, self).__init__(*args, **kwargs)

        # Filter the groups to only include those created by the current user
        if self.current_user:
            self.fields['groups'].queryset = UserGroup.objects.filter(created_by=self.current_user)

        # Update the choices for `user_role` based on the current user's role
        self.fields['user_role'].choices = self.get_role_choices()

        # Adjust the queryset for 'obrat_oddelek' based on the current user's permissions
        if self.current_user:
            if self.current_user.user_role == 'osnovni':
                relevant_obrati_oddelek = self.current_user.obrat_oddelek
                self.fields['obrat_oddelek'].queryset = ObratiOddelki.objects.filter(
                    obrati_oddelki_id=relevant_obrati_oddelek.obrati_oddelki_id
                ).order_by('obrat', 'oddelek')
            else:
                user_roles = UserAppRole.objects.filter(username=self.current_user)
                self.fields['obrat_oddelek'].queryset = ObratiOddelki.objects.filter(
                    aplikacije_obrat_oddelek__in=user_roles.filter(
                        role_name__in=['vodja', 'admin']
                    ).values_list('app_url_id__obrat_oddelek', flat=True)
                ).distinct().order_by('obrat', 'oddelek')

        self.fields['obrat_oddelek'].label_from_instance = self.get_obrat_oddelek_label

    def get_obrat_oddelek_label(self, obj):
        return f"{obj.obrat} - {obj.oddelek}"

    def get_role_choices(self):
        role_choices = [('osnovni', 'osnovni')]
        if self.current_user and self.current_user.user_role == 'vodja':
            role_choices.append(('vodja', 'vodja'))
        elif self.current_user and self.current_user.user_role == 'admin':
            role_choices.extend([('vodja', 'vodja'), ('admin', 'admin')])
        return role_choices

    def clean(self):
        cleaned_data = super().clean()
        obrat = cleaned_data.get('obrat')
        oddelek = cleaned_data.get('oddelek')
        if obrat and oddelek:
            try:
                obrat_oddelek = ObratiOddelki.objects.get(obrat=obrat, oddelek=oddelek)
                cleaned_data['obrat_oddelek'] = obrat_oddelek
            except ObratiOddelki.DoesNotExist:
                self.add_error('oddelek', 'The selected combination of obrat and oddelek is invalid.')

        return cleaned_data

class GroupForm(forms.ModelForm):
    class Meta:
        model = UserGroup
        fields = ['name', 'members']

    name = forms.CharField(
        label="Ime skupine", 
        max_length=255, 
        widget=forms.TextInput(attrs={'id': 'new_group_name_add_group'})
    )

    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'id': 'user_selection_add_group'}),
        label="Člani skupine",
    )