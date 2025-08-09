from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal

#########################
# Unmanaged Models (Existing external tables)
#########################

class PostajeStrojevTisna0104Montaza(models.Model):
    stroj = models.CharField(max_length=255)
    opis_stroja = models.CharField(max_length=255)
    postaja_stroja = models.CharField(max_length=255)
    opis_postaje = models.CharField(max_length=255)
    delovno_mesto = models.CharField(max_length=255)
    opis_delovnega_mesta = models.CharField(max_length=255)
    postaje_v_zaporedju = models.CharField(max_length=255)
    paralel = models.CharField(max_length=255)

    obmocje = models.CharField(max_length=255, blank=True, null=True)  
    rocna_montaza = models.BooleanField(default=False)
    zalogovnik = models.CharField(max_length=255)  

    # New fields
    production_reported_on_postaja = models.CharField(max_length=255, blank=True, null=True)
    postaja_logic_used = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'postaje_strojev_tisna0104_montaza'

class ZalogaSarza(models.Model):
    id = models.AutoField(primary_key=True)  # Auto-increment ID field
    dobavni_nalog = models.CharField(max_length=100, db_column='dobavni_nalog')
    del_id = models.CharField(max_length=100, db_column='del_id')
    sarza = models.CharField(max_length=100, db_column='sarza')
    del_opis = models.CharField(max_length=255, null=True, blank=True, db_column='del_opis')
    datum_dobave = models.DateField(db_column='datum_dobave')
    zaloga = models.DecimalField(max_digits=12, decimal_places=2, db_column='zaloga')

    class Meta:
        managed = True
        db_table = 'zaloga_sarza'
        unique_together = ('dobavni_nalog', 'del_id', 'sarza')


class TiBOMKosovnica(models.Model):
    artikel = models.CharField(max_length=100, db_column='artikel')
    opis = models.CharField(max_length=255, db_column='opis')
    verzija_razvojnega_artikla = models.CharField(max_length=100, db_column='Verzija razvojnega artikla')
    bom_kol = models.CharField(max_length=100, db_column='BOM kol')
    pozicija = models.CharField(max_length=100, db_column='Pozicija')
    del_id = models.CharField(max_length=100, db_column='del_id')
    del_opis = models.CharField(max_length=255, db_column='del_opis')
    kolicina = models.CharField(max_length=100, db_column='kolicina')
    enota = models.CharField(max_length=100, db_column='enota')
    skladisce = models.CharField(max_length=100, db_column='Skladišče')
    operacija = models.CharField(max_length=100, db_column='Operacija')
    datum_veljavnosti = models.CharField(max_length=100, db_column='Datum veljavnosti')
    datum_preteka = models.CharField(max_length=100, db_column='Datum preteka')
    phantom = models.CharField(max_length=100, db_column='Phantom')
    besedilo = models.CharField(max_length=255, db_column='Besedilo')

    class Meta:
        managed = True
        db_table = 'tibom1110_kosovnica'

class PreteklostZamenjavSarzTisna1160(models.Model):
    datum_transakcije = models.DateTimeField(db_column='datum_transakcije')
    seq_number = models.TextField(db_column='seq_number')
    zaposlen = models.FloatField(null=True, blank=True, db_column='zaposlen')
    zaposlen_ime = models.TextField(null=True, blank=True, db_column='zaposlen_ime')
    nalog = models.BigIntegerField(db_column='nalog')
    pozicija = models.BigIntegerField(null=True, blank=True, db_column='pozicija')
    del_id = models.TextField(db_column='del_id')
    del_opis = models.TextField(null=True, blank=True, db_column='del_opis')
    sarza = models.TextField(db_column='sarza')
    dejanska_kolicina = models.BigIntegerField(null=True, blank=True, db_column='dejanska_kolicina')
    zakljucena_kolicina = models.FloatField(null=True, blank=True, db_column='zakljucena_kolicina')
    problem_materiala = models.TextField(null=True, blank=True, db_column='problem_materiala')
    dan = models.DateTimeField(null=True, blank=True, db_column='dan')

    class Meta:
        managed = True
        db_table = 'preteklost_zamenjav_sarz_tisna1160'


#########################
# Managed Models (New Tables)
#########################

class Part(models.Model):
    del_id = models.CharField(max_length=100, primary_key=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    # If you need to block inbound transactions for this part:
    is_inbound_blocked = models.BooleanField(default=False)

    def __str__(self):
        return self.del_id

class Batch(models.Model):
    sarza = models.CharField(max_length=100)
    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    datum_dobave = models.DateField(null=True, blank=True)
    class Meta:
        unique_together = ('sarza', 'part')

class CurrentStock(models.Model):
    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    stroj = models.CharField(max_length=100)
    postaja = models.CharField(max_length=100)
    current_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    class Meta:
        unique_together = ('part', 'batch', 'stroj', 'postaja')

class CumulativeCount(models.Model):
    artikel = models.CharField(max_length=100)
    stroj = models.CharField(max_length=100)
    postaja = models.CharField(max_length=100)
    del_id = models.CharField(max_length=100)
    sarza = models.CharField(max_length=100)
    cumulative_count = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.0'))

    class Meta:
        unique_together = ('artikel', 'stroj', 'postaja', 'del_id', 'sarza')


    def __str__(self):
        return f"{self.artikel} on {self.stroj} at {self.postaja} - {self.cumulative_count}"

class InboundTransaction(models.Model):
    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    stroj = models.CharField(max_length=100)
    postaja = models.CharField(max_length=100)
    quantity_added = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    day_date = models.DateField(default=timezone.now)

class ProductionTransaction(models.Model):
    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    stroj = models.CharField(max_length=100)
    postaja = models.CharField(max_length=100)
    artikel = models.CharField(max_length=100)
    quantity_consumed = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    day_date = models.DateField(default=timezone.now)

class AdjustmentTransaction(models.Model):
    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    stroj = models.CharField(max_length=100)
    postaja = models.CharField(max_length=100)
    quantity_adjustment = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    day_date = models.DateField(default=timezone.now)

class StrojArtikelSarzaMoznosti(models.Model):
    stroj = models.CharField(max_length=100)
    artikel = models.CharField(max_length=100)
    sarza = models.CharField(max_length=100)
    del_id = models.CharField(max_length=100)
    nalog = models.BigIntegerField()
    class Meta:
        unique_together = ('stroj', 'artikel', 'sarza', 'del_id', 'nalog')

class StrojArtikelSarzaTrenutno(models.Model):
    stroj = models.CharField(max_length=100)
    artikel = models.CharField(max_length=100)
    sarza = models.CharField(max_length=100)
    del_id = models.CharField(max_length=100)
    class Meta:
        unique_together = ('stroj', 'artikel', 'del_id')
        db_table = 'stroj_artikel_sarza_trenutno'

###################################
# Virtual Batch Allocation Models
###################################
class InboundVirtualBatchAllocation(models.Model):
    """
    Temporarily store inbound quantities for blocked parts.
    The supervisor will later allocate these to virtual batches.

    Example:
    - User sets is_inbound_blocked=True for a part
    - When inbound arrives, instead of creating InboundTransaction,
      we create InboundVirtualBatchAllocation entries.
    - The user then divides the quantity among several virtual batches (sarza + suffix).
    - After allocation is done, we convert these allocations into real InboundTransactions.
    """
    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    original_batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    stroj = models.CharField(max_length=100)
    postaja = models.CharField(max_length=100)
    total_inbound_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    allocated = models.BooleanField(default=False)

class InboundVirtualBatchItem(models.Model):
    """
    Allocations to particular virtual batches:
    e.g. sarza12_{location_1}, sarza12_{location_2}
    """
    allocation = models.ForeignKey(InboundVirtualBatchAllocation, on_delete=models.CASCADE, related_name='items')
    virtual_sarza = models.CharField(max_length=200)  # e.g. sarza + suffix
    quantity = models.DecimalField(max_digits=12, decimal_places=2)

###################################
# Signals to update CurrentStock
###################################
def update_current_stock(part_id, batch_id, stroj, postaja, quantity_change):
    obj, created = CurrentStock.objects.get_or_create(
        part_id=part_id,
        batch_id=batch_id,
        stroj=stroj,
        postaja=postaja,
        defaults={'current_stock': 0}
    )
    obj.current_stock = obj.current_stock + quantity_change
    obj.save()

@receiver(post_save, sender=ProductionTransaction)
def decrease_stock_on_production(sender, instance, created, **kwargs):
    if created:
        update_current_stock(
            part_id=instance.part_id,
            batch_id=instance.batch_id,
            stroj=instance.stroj,
            postaja=instance.postaja,
            quantity_change=-instance.quantity_consumed
        )

@receiver(post_save, sender=AdjustmentTransaction)
def adjust_stock_on_adjustment(sender, instance, created, **kwargs):
    if created:
        update_current_stock(
            part_id=instance.part_id,
            batch_id=instance.batch_id,
            stroj=instance.stroj,
            postaja=instance.postaja,
            quantity_change=instance.quantity_adjustment
        )

@receiver(post_save, sender=InboundTransaction)
def increase_stock_on_inbound(sender, instance, created, **kwargs):
    if created:
        update_current_stock(
            part_id=instance.part_id,
            batch_id=instance.batch_id,
            stroj=instance.stroj,
            postaja=instance.postaja,
            quantity_change=instance.quantity_added
        )
