from django.db import models

class Game(models.Model):
    room_name = models.CharField(max_length=100, primary_key=True)
    player1_id = models.IntegerField(null=True)
    player2_id = models.IntegerField(null=True)
    winner_id = models.IntegerField(null=True)
    start_time = models.DateTimeField(auto_now=False, auto_now_add=True)
    end_time = models.DateTimeField(auto_now=False, auto_now_add=False, null=True)
    status = models.CharField(max_length=10) #running, finished, aborted
