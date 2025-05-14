from django.db import models

class Building(models.Model):
    name = models.CharField(max_length=255, verbose_name="Tên tòa nhà")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Địa chỉ")
    def __str__(self):
        return self.name

class Floor(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="floors", verbose_name="Tòa nhà")
    number = models.CharField(max_length=20, verbose_name="Tầng")
    def __str__(self):
        return f"{self.building.name} - Tầng {self.number}"

class Room(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="rooms", verbose_name="Tầng")
    name = models.CharField(max_length=100, verbose_name="Tên phòng")
    zone = models.CharField(max_length=100, blank=True, null=True, verbose_name="Khu vực")
    def __str__(self):
        return f"{self.floor.building.name} - Tầng {self.floor.number} - {self.name}"
