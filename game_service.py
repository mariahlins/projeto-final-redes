import threading
from typing import Callable
from tictactoe import TickTacToe

class GameService:
    """
    Orquestra: liga callbacks do TickTacToe a um event_sink (ex.: Queue.put).
    Exponibiliza comandos seguros para a UI.
    """
    def __init__(self, event_sink: Callable[[dict], None]):
        self.events = event_sink
        self.game = TickTacToe()

        # callbacks -> eventos
        self.game.on_board = lambda board, turn: self.events({"type": "board_update", "board": board, "turn": turn})
        self.game.on_message = lambda text: self.events({"type": "message", "text": text})
        self.game.on_over = lambda winner: self.events({"type": "game_over", "winner": winner})
        self.game.on_connection = lambda state: self.events({"type": "connection", "state": state})
        self.game.on_rematch = self._on_rematch

    def _on_rematch(self, etype: str, payload: dict):
        # repassa para a UI com tipos específicos
        if etype == "offer":
            self.events({"type": "rematch_offer", **payload})
        elif etype == "accepted":
            self.events({"type": "rematch_accept", **payload})
        elif etype == "declined":
            self.events({"type": "rematch_decline"})
        elif etype == "start":
            self.events({"type": "rematch_start", **payload})

    # comandos (UI -> serviço)
    def host(self, host: str, port: int):
        threading.Thread(target=self.game.host_game, args=(host, port), daemon=True).start()

    def connect(self, host: str, port: int):
        threading.Thread(target=self.game.connect_to_game, args=(host, port), daemon=True).start()

    def make_move(self, r: int, c: int):
        self.game.enqueue_local_move(r, c)

    def request_rematch(self, swap: bool = False):
        self.game.request_rematch(swap=swap)

    def respond_rematch(self, accept: bool, swap: bool = False):
        self.game.respond_rematch(accept=accept, swap=swap)

    def quit(self):
        self.game.shutdown()
