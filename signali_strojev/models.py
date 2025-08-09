from django.db import models
from django.utils.text import slugify

class TimConfig(models.Model):
    team_name = models.CharField(max_length=255, unique=True)
    team_label = models.CharField(max_length=255)
    vodja = models.CharField(max_length=255)
    ad_username = models.CharField(max_length=255)
    oddelek = models.CharField(max_length=255)
    obrat = models.CharField(max_length=255)
    team_label_slug = models.SlugField(max_length=255, blank=True)
    team_name_slug = models.SlugField(max_length=255, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.team_label_slug:
            self.team_label_slug = slugify(self.team_label)
        if not self.team_name_slug:
            self.team_name_slug = slugify(self.team_name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.team_name

class TimDefinition(models.Model):
    tim_config = models.ForeignKey(TimConfig, on_delete=models.CASCADE, related_name='definitions')
    ime_tabele = models.CharField(max_length=255)
    operacija = models.IntegerField(blank=True, null=True)
    opravilo = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.tim_config.team_name} - {self.ime_tabele}"

class StrojEntry(models.Model):
    tim_definition = models.ForeignKey(TimDefinition, on_delete=models.CASCADE, related_name='stroj_entries')
    stroj = models.CharField(max_length=255)
    postaja = models.CharField(max_length=255, blank=True, null=True)
    is_delovno_mesto = models.BooleanField(default=False)

    def __str__(self):
        return self.stroj
    
class StrojZastojOpombaEntry(models.Model):
    stroj = models.CharField(max_length=255)
    artikel = models.CharField(max_length=255, blank=True, null=True)
    izmena = models.IntegerField()
    opomba = models.TextField(blank=True)
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    zastoj_entries = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.stroj} - Izmena {self.izmena} ({self.start_date} to {self.end_date})"
