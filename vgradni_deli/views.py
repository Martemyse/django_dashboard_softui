from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

import json
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from .models import PostajeStrojevTisna0104Montaza

from .models import (
    Part, Batch, CurrentStock, InboundTransaction, ProductionTransaction, AdjustmentTransaction,
    StrojArtikelSarzaMoznosti, StrojArtikelSarzaTrenutno,
    InboundVirtualBatchAllocation, InboundVirtualBatchItem
)
from .serializers import (
    PartSerializer, BatchSerializer, CurrentStockSerializer,
    InboundTransactionSerializer, ProductionTransactionSerializer, AdjustmentTransactionSerializer,
    StrojArtikelSarzaMoznostiSerializer, StrojArtikelSarzaTrenutnoSerializer,
    InboundVirtualBatchAllocationSerializer, InboundVirtualBatchItemSerializer
)

class PartViewSet(viewsets.ModelViewSet):
    queryset = Part.objects.all()
    serializer_class = PartSerializer

class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer

class CurrentStockViewSet(viewsets.ModelViewSet):
    queryset = CurrentStock.objects.all()
    serializer_class = CurrentStockSerializer

class InboundTransactionViewSet(viewsets.ModelViewSet):
    queryset = InboundTransaction.objects.all()
    serializer_class = InboundTransactionSerializer

class ProductionTransactionViewSet(viewsets.ModelViewSet):
    queryset = ProductionTransaction.objects.all()
    serializer_class = ProductionTransactionSerializer

class AdjustmentTransactionViewSet(viewsets.ModelViewSet):
    queryset = AdjustmentTransaction.objects.all()
    serializer_class = AdjustmentTransactionSerializer

class StrojArtikelSarzaMoznostiViewSet(viewsets.ModelViewSet):
    queryset = StrojArtikelSarzaMoznosti.objects.all()
    serializer_class = StrojArtikelSarzaMoznostiSerializer

class StrojArtikelSarzaTrenutnoViewSet(viewsets.ModelViewSet):
    queryset = StrojArtikelSarzaTrenutno.objects.all()
    serializer_class = StrojArtikelSarzaTrenutnoSerializer

    @action(detail=False, methods=['post'])
    def set_active_sarza(self, request):
        stroj = request.data.get('stroj')
        artikel = request.data.get('artikel')
        del_id = request.data.get('del_id')
        sarza = request.data.get('sarza')
        nalog = request.data.get('nalog')

        if not all([stroj, artikel, del_id, sarza, nalog]):
            return Response({"error": "Missing parameters"}, status=status.HTTP_400_BAD_REQUEST)

        obj, created = StrojArtikelSarzaTrenutno.objects.update_or_create(
            stroj=stroj, artikel=artikel, del_id=del_id, nalog=nalog,
            defaults={'sarza': sarza}
        )
        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InboundVirtualBatchAllocationViewSet(viewsets.ModelViewSet):
    queryset = InboundVirtualBatchAllocation.objects.all()
    serializer_class = InboundVirtualBatchAllocationSerializer

    @action(detail=True, methods=['post'])
    def finalize_allocation(self, request, pk=None):
        """
        Finalize the allocation:
        Create InboundTransaction records from the virtual batch items.
        This will update CurrentStock via signals.
        """
        allocation = self.get_object()
        if allocation.allocated:
            return Response({"error": "Already allocated"}, status=status.HTTP_400_BAD_REQUEST)

        items_data = request.data.get('items', [])
        # items_data = [{'virtual_sarza': 'sarza12_{loc1}', 'quantity': '100'}]
        with transaction.atomic():
            total_assigned = 0
            for item_data in items_data:
                virtual_sarza = item_data['virtual_sarza']
                quantity = Decimal(item_data['quantity'])
                # Create a new batch for this virtual sarza if needed
                part = allocation.part
                new_batch, _ = Batch.objects.get_or_create(
                    sarza=virtual_sarza,
                    part=part,
                    defaults={'datum_dobave': timezone.now().date()}
                )
                # Create inbound transaction for this allocated quantity
                InboundTransaction.objects.create(
                    part=part,
                    batch=new_batch,
                    stroj=allocation.stroj,
                    postaja=allocation.postaja,
                    quantity_added=quantity,
                    nalog=allocation.nalog
                )
                total_assigned += quantity

                # Save the allocation items for record
                InboundVirtualBatchItem.objects.create(
                    allocation=allocation,
                    virtual_sarza=virtual_sarza,
                    quantity=quantity
                )

            if total_assigned != allocation.total_inbound_quantity:
                # If not fully assigned, you might raise an error or allow partial allocation
                # For now, let's assume full allocation is required:
                return Response({"error": "Assigned quantity does not match total inbound quantity"}, status=status.HTTP_400_BAD_REQUEST)

            allocation.allocated = True
            allocation.save()

        return Response({"message": "Allocation finalized successfully"}, status=status.HTTP_200_OK)

def konfiguracija_vgradni_deli(request, safe_obrat, safe_oddelek):
    # Fetch all data from PostajeStrojevTisna0104Montaza
    montaza_data = list(PostajeStrojevTisna0104Montaza.objects.values())
    # Convert to JSON string safely
    row_data_json = json.dumps(montaza_data, cls=DjangoJSONEncoder)

    context = {
        'rowData': row_data_json,
        'safe_obrat': safe_obrat,
        'safe_oddelek': safe_oddelek
    }
    return render(request, 'pages/konfiguracija_vgradni_deli.html', context)

def pregled_vgradni_deli(request, safe_obrat, safe_oddelek):
    context = {
        'safe_obrat': safe_obrat,
        'safe_oddelek': safe_oddelek,
    }
    return render(request, 'pages/pregled_vgradni_deli.html', context)

@csrf_exempt
def update_montaza_cell(request):
    if request.method == 'POST':
        # Expecting JSON: { "id": int, "field": str, "value": any }
        data = json.loads(request.body.decode('utf-8'))
        record_id = data.get('id')
        field = data.get('field')
        value = data.get('value')

        if record_id and field:
            # Update the record in DB
            try:
                obj = PostajeStrojevTisna0104Montaza.objects.get(id=record_id)
                # Convert boolean fields properly
                if field == 'rocna_montaza':
                    value = True if value in [True, 'true', 'True', 1] else False
                setattr(obj, field, value)
                obj.save()
                return JsonResponse({'status': 'success'})
            except PostajeStrojevTisna0104Montaza.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Record not found'}, status=404)
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)