import json
import uuid
import random
import asyncio

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from collections import defaultdict
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q
from datetime import date
from . import models

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.player_num = int(self.scope['url_route']['kwargs']['player_num'])
        self.nf7_2 = 2                                                                #represent the number of hezz2 but can incerement if the oponent set other hezz2
        self.sb3a = False                                                             #if the player pu sb3a t7km it turn to True until the round Done
        self.selected_card = None
        self.timeout_task = None

        isgame = await self.isgame(self.room_name)

        if isgame == 0:
            return

        self.robot = await self.robot_game(self.room_name)

        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        await self.increment_group_size(self.room_name)

        await self.accept()

        if isgame == 2:
            await self.reconnected()
        elif await self.get_group_size(self.room_name) == 2 or self.robot:
            await self.init_game(self.player_num)

    async def disconnect(self, close_code):
        await self.channel_layer.group_send(
            self.room_name,
            {"type": "abort.game", "ply_num": self.player_num}
        )
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )
        await self.decrement_group_size(self.room_name)
        await self.status_game(self.room_name)

    async def reconnected(self):
        await self.channel_layer.group_send(
            self.room_name,
            {"type": "reconnect.game", "ply_num": self.player_num}
        )

    async def reconnect_game(self, event):
        ply_num = event['ply_num']
        if ply_num != self.player_num:
            if self.timeout_task:
                self.timeout_task.cancel()
                self.timeout_task = None
            data = {
                "init_card": self.init_card,
                "p1_cards": self.player1_cards,
                "p2_cards": self.player2_cards,
                "cards": self.cards,
                "turn": self.turn,
                "selected_card": self.selected_card,
                "card_type": self.card_type,
                "nf7_2": self.nf7_2
                }

            await self.channel_layer.group_send(
                self.room_name,
                {"type": "cards.sender", "data": data}
            )
            await self.send_status("reconnected")

    async def abort_game(self, event):
        ply_num = event['ply_num']
        if ply_num != self.player_num:
            if self.timeout_task:
                self.timeout_task.cancel()
            self.timeout_task = asyncio.create_task(self.timer(10, True))
        await self.send_status("aborted")

    async def receive(self, text_data):
        data = json.loads(text_data)

        if 'action' in data:
            await self.game_logic(data['action'])     

    async def game_logic(self, card, robot = False):
        index = False
        player_num = self.player_num if robot == False else 1
        if not await self.error_checks(card, player_num):
            return
        if self.sb3a is True:
            self.card_type = card
            self.sb3a = False
            index = True
            self.turn = 2 if self.turn == 1 else 1
        elif card == "nf7":
            if self.selected_card is not None:
                await self.send_error("not compatible card")
                return
            index = True
            if await self.nf7(player_num, 1):
                return
            self.turn = 2 if self.turn == 1 else 1
        elif await self.check_card(card): #compatible card check
            self.cards.insert(random.randint(0, len(self.cards) - 1) if len(self.cards) != 0 else 0, self.init_card)
            self.init_card = card
            if player_num == 1:
                self.player1_cards.remove(card)
            else:
                self.player2_cards.remove(card)
            if len(self.player2_cards) == 0 or len(self.player1_cards) == 0:
                await self.save_game(2) if len(self.player2_cards) == 0 else await self.save_game(1)
                await self.channel_layer.group_send(
                    self.room_name,
                    {"type": "end.game", "ply1": (len(self.player1_cards) == 0)}
                )
            self.selected_card = None
            if card[2:] == '1':
                self.selected_card = await self.ropo(player_num)
            elif card[2:] == '2':
                self.selected_card = await self.hezz2(player_num)
            elif card[2:] == '7':
                self.selected_card = await self.sb3a_t7km(player_num)
                if self.sb3a == True:
                    return
            else:
                self.turn = 2 if self.turn == 1 else 1
        else:
            await self.send_error("not compatible card")
            return
        if index is False:
            self.card_type = self.init_card[:2]
        data = {
            "init_card": self.init_card,
            "p1_cards": self.player1_cards,
            "p2_cards": self.player2_cards,
            "cards": self.cards,
            "turn": self.turn,
            "selected_card": self.selected_card,
            "card_type": self.card_type,
            "nf7_2": self.nf7_2
            }

        await self.channel_layer.group_send(
            self.room_name,
            {"type": "cards.sender", "data": data}
        )

    async def nf7(self, player_num, num):
        if len(self.cards) < num:
            await self.send_error("mab9awch cartat ajmi")
            return True
        elif player_num == 1:
            for i in range(num):
                new_card = self.cards.pop(random.randint(0, len(self.cards) - 1))
                self.player1_cards.append(new_card)
        else:
            for i in range(num):
                new_card = self.cards.pop(random.randint(0, len(self.cards) - 1))
                self.player2_cards.append(new_card)
        return False

    async def sb3a_t7km(self, player_num):
        selected_card = await self.in_cards(self.player2_cards, "7") if player_num == 1 else await self.in_cards(self.player1_cards, "7")
        if not selected_card:
            await self.send_status("chno bghiti")
            self.sb3a = True
        else:
            self.turn = 2 if self.turn == 1 else 1
        return '7' if selected_card else None

    async def end_game(self, event):
        ply1 = event['ply1']
        if self.timeout_task:
            self.timeout_task.cancel()
        if self.player_num == 1:
            await self.send_status("win" if ply1 else "lose")
        else:
            await self.send_status("lose" if ply1 else "win")
        await self.close(1000)

    async def hezz2(self, player_num):
        selected_card = await self.in_cards(self.player2_cards, "2") if player_num == 1 else await self.in_cards(self.player1_cards, "2")
        if not selected_card:
            await self.nf7(2, self.nf7_2) if player_num == 1 else await self.nf7(1, self.nf7_2)
            self.nf7_2 = 2
        else:
            self.nf7_2 += 2
            self.turn = 2 if self.turn == 1 else 1
        return '2' if selected_card else None

    async def ropo(self, player_num):
        selected_card = None
        if player_num == 1:
            selected_card = await self.in_cards(self.player2_cards, "1")
            if selected_card:
                self.turn = 2 if self.turn == 1 else 1
        else:
            selected_card = await self.in_cards(self.player1_cards, "1")
            if selected_card:
                self.turn = 2 if self.turn == 1 else 1
        return '1' if selected_card else None

    async def in_cards(self, cards, number):
        for card in cards:
            if card[2:] == number:
                return card
        return None

    async def error_checks(self, card, player_num):
        if self.turn != player_num:
            await self.send_error("not your turn")
            return False
        if self.sb3a is True:
            if card != 'sw' and card != 'cu' and card != 'st' and card != 'go':
                await self.send_error("khtar chno bghiti lfo9")
                return False
            return True
        if card == "nf7":
            return True
        if player_num == 1 and card not in self.player1_cards:
            await self.send_error("not part of your cards")
            return False
        if player_num == 2 and card not in self.player2_cards:
            await self.send_error("not part of your cards")
            return False
        return True

    async def check_card(self, card):
        if self.selected_card:
            if card[2:] != self.selected_card:
                return False
        if card[:2] == self.card_type:
            return True
        if card[2:] == self.init_card[2:]:
            return True
        return False

    async def send_error(self, error):
        await self.send(text_data=json.dumps({
            "error": error,
        }))

    async def send_status(self, msg):
        await self.send(text_data=json.dumps({
            "status": msg,
        }))

    async def init_game(self, player_num):
        self.cards = [
            "sw1", "sw2", "sw3", "sw4", "sw5", "sw6", "sw7", "sw10", "sw11", "sw12",
            "cu1", "cu2", "cu3", "cu4", "cu5", "cu6", "cu7", "cu10", "cu11", "cu12",
            "st1", "st2", "st3", "st4", "st5", "st6", "st7", "st10", "st11", "st12",
            "go1", "go2", "go3", "go4", "go5", "go6", "go7", "go10", "go11", "go12",
        ]
        self.player1_cards, self.player2_cards, self.init_card = await self.generate_card()
        self.turn = random.randint(1, 2)

        data = {
            "init_card": self.init_card,
            "p1_cards": self.player1_cards,
            "p2_cards": self.player2_cards,
            "cards": self.cards,
            "turn": self.turn,
            "selected_card": None,
            "card_type": self.card_type,
            "nf7_2": self.nf7_2
            }
        
        await self.channel_layer.group_send(
            self.room_name,
            {"type": "cards.sender", "data": data}
        )

    async def cards_sender(self, event):
        data = event['data']

        self.selected_card = data['selected_card']
        self.player1_cards = data['p1_cards']
        self.player2_cards = data['p2_cards']
        self.init_card = data['init_card']
        self.card_type = data['card_type']
        self.nf7_2 = data['nf7_2']
        self.cards = data['cards']
        self.turn = data['turn']
        
        if self.player_num == self.turn:
            if (self.timeout_task):
                self.timeout_task.cancel()
            self.timeout_task = asyncio.create_task(self.timer())
        else:
            if self.timeout_task:
                self.timeout_task.cancel()
                self.timeout_task = None

        if self.player_num == 1:
            await self.send(text_data=json.dumps(
                {
                    "init_card": data['init_card'],
                    "p1_cards": data['p1_cards'],
                    "p2_cards_len": len(data['p2_cards']),
                    "turn": data['turn'],
                    "select_card": data['selected_card'],
                    "card_type": data['card_type'],
                }
            ))
        else:
            await self.send(text_data=json.dumps(
                {
                    "init_card": data['init_card'],
                    "p1_cards": data['p2_cards'],
                    "p2_cards_len": len(data['p1_cards']),
                    "turn": data['turn'],
                    "select_card": data['selected_card'],
                    "card_type": data['card_type'],
                }
            ))
        if self.turn == 1 and self.robot:
            await asyncio.sleep(random.randint(1, 3))
            for card in self.player1_cards:
                if await self.check_card(card):
                    await self.game_logic(card, True)
                    if card[2:] == '7' and self.turn == 1:
                        await self.game_logic(["sw", "st", "go", "cu"][random.randint(0, 3)], True)
                    return
            await self.game_logic("nf7", True)

    async def timer(self, timeout = 60, index = False):
        try:
            await asyncio.sleep(timeout)
            if index == False:
                await self.save_game(2) if self.player_num == 1 else await self.save_game(1)
                await self.channel_layer.group_send(
                    self.room_name,
                    {"type": "end.game", "ply1": (self.player_num == 2)}
                )
            else:
                await self.save_game(2) if self.player_num == 2 else await self.save_game(1)
                await self.channel_layer.group_send(
                    self.room_name,
                    {"type": "end.game", "ply1": (self.player_num == 1)}
                )

        except asyncio.CancelledError:
            pass

    async def generate_card(self):
        p1_cards = []
        p2_cards = []
        
        for i in range(4):
            n = random.randint(0, len(self.cards) - 1)
            p1_cards.append(self.cards.pop(n))
            n = random.randint(0, len(self.cards) - 1)
            p2_cards.append(self.cards.pop(n))
        n = random.randint(0, len(self.cards) - 1)
        init_card = self.cards.pop(n)
        self.card_type = init_card[:2]
        return p1_cards, p2_cards, init_card
    
    async def increment_group_size(self, room_name):
        key = f"group_size_{room_name}"
        size = cache.get(key, 0)
        cache.set(key, size + 1)

    async def decrement_group_size(self, room_name):
        key = f"group_size_{room_name}"
        size = cache.get(key, 0)
        cache.set(key, max(size - 1, 0))

    async def get_group_size(self, room_name):
        key = f"group_size_{room_name}"
        size = cache.get(key, 0)
        return size

    @database_sync_to_async
    def status_game(self, room_name, status = "running", newstatus = "aborted"):
        try:
            game = models.Game.objects.filter(room_name=room_name).first()
            if game:
                if game.status == status:
                    game.status = newstatus
                    game.save()
        except Exception as e:
            print("Error: ", e)
                    
    @database_sync_to_async
    def isgame(self, room_name):
        game = models.Game.objects.filter(room_name=room_name).first()
        if game:
            if game.status == "running":
                return 1
            if game.status == "aborted":
                return 2
        return 0
    
    @database_sync_to_async
    def robot_game(self, room_name):
        game = models.Game.objects.filter(room_name=room_name).first()
        if game and game.player1_id == 0:
            return True
        return False

    @database_sync_to_async
    def save_game(self, winner_num):
        try:
            game = models.Game.objects.filter(room_name=self.room_name).first()
            if game:
                winner_id = game.player1_id if winner_num == 1 else game.player1_id
                game.winner_id = winner_id
                game.end_time = timezone.now()
                game.status = "finished"
                game.save()
        except Exception as e:
            print("Error: ", e)

class MatchMakerConsumer(AsyncWebsocketConsumer):
    waiting_list = defaultdict(list)

    async def connect(self):
        self.player_id = self.scope['url_route']['kwargs']['player_id']
        await self.accept()

    async def disconnect(self, close_code):
        for game_type in self.waiting_list:
            if self.channel_name in [channel for channel, _ in self.waiting_list[game_type]]:
                self.waiting_list[game_type] = [pair for pair in self.waiting_list[game_type] if pair[0] != self.channel_name]

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data['action']

        if action == 'find_game':
            if ('robot' in data and data['robot'] == "true"):
                await self.bot_match()
                return
            game_type = data['game_type']
            await self.find_match(game_type)
    
    async def bot_match(self):
        room_game = f'game_{uuid.uuid4()}'

        await self.start_game(room_game, 0, self.player_id)

        await self.send(text_data=json.dumps({
            "type": "match_found",
            "room": room_game,
            "player_number": 2,
        }))

        await self.close(1000)

    async def find_match(self, game_type):
        game = await self.get_game()
        if game:
            await self.send(json.dumps({
                "type": "match_found",
                "room": game["room"],
                "player_number": game["player_number"]
            }))

            await self.close(1000)

            return
        self.waiting_list[game_type].append((self.channel_name, self.player_id))
        if len(self.waiting_list[game_type]) >= 2:

            player1 = self.waiting_list[game_type].pop(0)
            player2 = self.waiting_list[game_type].pop(0)

            if player1[1] == player2[1]:
                return

            room_game = f'game_{uuid.uuid4()}'

            channel_layer = get_channel_layer()

            await self.start_game(room_game, player1[1], player2[1])

            await channel_layer.send(
                player1[0],
                {
                    "type": "match_found",
                    "room": room_game,
                    "player_number": 1
                }
            )

            await channel_layer.send(
                player2[0],
                {
                    "type": "match_found",
                    "room": room_game,
                    "player_number": 2
                }
            )
        else:
            await self.send(json.dumps({
                "type": "status",
                "message": "Searching for opponent..."
            }))

    async def match_found(self, event):

        await self.send(json.dumps({
            "type": "match_found",
            "room": event["room"],
            "player_number": event["player_number"]
        }))

        await self.close(1000)

    @database_sync_to_async
    def start_game(self, room_name, player1_id, player2_id):

        game = models.Game(
            room_name = room_name,
            player1_id = player1_id,
            player2_id = player2_id,
            winner_id = None,
            status = "running"
        )
        try:
            game.save()
            print(f"New game created: {game.room_name}")
        except Exception as e:
            print(f"Error creating game: {e}")
            return False
        return True

    @database_sync_to_async
    def get_game(self):
        game = models.Game.objects.filter(
            Q(player1_id=self.player_id) | Q(player2_id=self.player_id),
            status="aborted"
        ).first()
        if game:
            return {"room": game.room_name, "player_number": 2 if game.player2_id == int(self.player_id) else 1}
        return None
###########