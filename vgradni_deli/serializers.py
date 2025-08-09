from rest_framework import serializers
from .models import (
    Part, Batch, CurrentStock, InboundTransaction, ProductionTransaction, AdjustmentTransaction,
    StrojArtikelSarzaMoznosti, StrojArtikelSarzaTrenutno,
    InboundVirtualBatchAllocation, InboundVirtualBatchItem
)

class PartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Part
        fields = '__all__'

class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = '__all__'

class CurrentStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrentStock
        fields = '__all__'

class InboundTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InboundTransaction
        fields = '__all__'

class ProductionTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionTransaction
        fields = '__all__'

class AdjustmentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdjustmentTransaction
        fields = '__all__'

class StrojArtikelSarzaMoznostiSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrojArtikelSarzaMoznosti
        fields = '__all__'

class StrojArtikelSarzaTrenutnoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrojArtikelSarzaTrenutno
        fields = '__all__'

class InboundVirtualBatchItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InboundVirtualBatchItem
        fields = '__all__'

class InboundVirtualBatchAllocationSerializer(serializers.ModelSerializer):
    items = InboundVirtualBatchItemSerializer(many=True, read_only=True)
    class Meta:
        model = InboundVirtualBatchAllocation
        fields = '__all__'
