# serializers.py
from rest_framework import serializers
from .models import TimConfig, TimDefinition, StrojEntry

class StrojEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = StrojEntry
        fields = '__all__'

class TimDefinitionSerializer(serializers.ModelSerializer):
    stroj_entries = StrojEntrySerializer(many=True, read_only=True)

    class Meta:
        model = TimDefinition
        fields = '__all__'

class TimConfigSerializer(serializers.ModelSerializer):
    definition = TimDefinitionSerializer(read_only=True)

    class Meta:
        model = TimConfig
        fields = '__all__'
