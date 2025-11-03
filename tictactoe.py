import socket
import threading
from queue import Queue, Empty
from typing import Callable, Optional

class TickTacToe:
    """
    Lógica do jogo + rede (peer-to-peer).
    - NÃO usa input(); UI alimenta jogadas via Queue.
    - Mantém o socket aberto ao final da partida para permitir revanche.
    - Protocolo texto: "r,c", "END:X|O|DRAW", "BYE", "REMATCH", "REMATCH:SWAP",
      "REMATCH:OK", "REMATCH:OK:SWAP", "REMATCH:NO".
    """
    def __init__(self):
        self._reset_board()
        self.you = "X"
        self.opponent = "O"

        # Callbacks
        self.on_board: Callable[[list[list[str]], str], None] = lambda board, turn: None
        self.on_message: Callable[[str], None] = lambda text: None
        self.on_over: Callable[[Optional[str]], None] = lambda winner: None
        self.on_connection: Callable[[str], None] = lambda state: None  # connecting/connected/disconnected/error
        # Eventos de revanche: etype in {"offer","accepted","declined","start"}
        self.on_rematch: Callable[[str, dict], None] = lambda etype, payload: None

        # fila para jogadas locais (UI)
        self._move_queue: Queue[tuple[int,int]] = Queue()

        # rede
        self._sock: Optional[socket.socket] = None
        self._server_sock: Optional[socket.socket] = None  # somente para host
        self._net_thread: Optional[threading.Thread] = None

        # flags de ciclo de vida
        self._lock = threading.Lock()
        self._running = False
        self._session_active = False     # há sessão conectada?
        self._hosting_in_progress = False

    # ===================== API externa (UI/Service) =====================

    def enqueue_local_move(self, r: int, c: int):
        self._move_queue.put((r, c))

    def host_game(self, host: str, port: int):
        if self._session_active or self._hosting_in_progress or self._sock:
            self.on_message("Já existe uma sessão ativa.")
            return
        self._hosting_in_progress = True
        self.on_connection("connecting")
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock = server
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((host, port))
            server.listen(1)
            self.on_message(f"Esperando conexão em {host}:{port}...")
            client, addr = server.accept()
            # fechamos o socket de escuta (não precisamos mais)
            try:
                server.close()
            finally:
                self._server_sock = None
            self.on_message(f"Oponente conectado: {addr}")
            self.you, self.opponent = "X", "O"
            self._start_net_loop(client)
        except OSError as e:
            self.on_connection("error")
            self.on_message(f"Falha ao hostear: {e}")
            # limpa server_sock se ainda aberto
            try:
                if self._server_sock:
                    self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
            self._hosting_in_progress = False
        except Exception as e:
            self.on_connection("error")
            self.on_message(f"Erro ao hostear: {e}")
            self._hosting_in_progress = False
        finally:
            # se conectou com sucesso, _start_net_loop assume; senão, libera a flag
            if self._sock is None:
                self._hosting_in_progress = False

    def connect_to_game(self, host: str, port: int):
        if self._session_active or self._hosting_in_progress or self._sock:
            self.on_message("Já existe uma sessão ativa.")
            return
        self.on_connection("connecting")
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.on_message(f"Conectando a {host}:{port}...")
            client.connect((host, port))
            self.on_message("Conectado! Você é O.")
            self.you, self.opponent = "O", "X"
            self._start_net_loop(client)
        except ConnectionRefusedError:
            self.on_connection("error")
            self.on_message("Conexão recusada (ninguém hosteando nesse endereço/porta).")
        except Exception as e:
            self.on_connection("error")
            self.on_message(f"Erro ao conectar: {e}")

    def request_rematch(self, swap: bool = False):
        """Solicita revanche mantendo o socket aberto. swap=True troca X/O."""
        if not self._session_active or not self._sock:
            self.on_message("Sem sessão ativa para pedir revanche.")
            return
        token = "REMATCH:SWAP" if swap else "REMATCH"
        try:
            self._sock.send(token.encode("utf-8"))
            self.on_message("Pedido de revanche enviado.")
        except Exception:
            self.on_message("Não foi possível enviar pedido de revanche.")

    def respond_rematch(self, accept: bool, swap: bool = False):
        """Responde a um pedido de revanche recebido."""
        if not self._session_active or not self._sock:
            return
        try:
            if accept:
                token = "REMATCH:OK:SWAP" if swap else "REMATCH:OK"
                self._sock.send(token.encode("utf-8"))
                self._start_rematch(swap=swap, initiator=False)
                self.on_rematch("accepted", {"swap": swap})
            else:
                self._sock.send(b"REMATCH:NO")
                self.on_rematch("declined", {})
        except Exception:
            self.on_message("Falha ao responder ao pedido de revanche.")

    def shutdown(self):
        """Fecha conexão/threads de forma limpa."""
        self._running = False
        self._session_active = False
        try:
            if self._sock:
                try:
                    self._sock.send(b"BYE")
                except Exception:
                    pass
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self._sock.close()
        except Exception:
            pass
        self._sock = None
        try:
            if self._server_sock:
                self._server_sock.close()
        except Exception:
            pass
        self._server_sock = None
        self.on_connection("disconnected")

    # ===================== Internos =====================

    def _reset_board(self):
        self.board = [[" "," "," "],[" "," "," "],[" "," "," "]]
        self.turn = "X"
        self.winner: Optional[str] = None
        self.game_over = False
        self.counter = 0

    def _start_net_loop(self, sock: socket.socket):
        self._sock = sock
        self._sock.settimeout(0.3)
        self._running = True
        self._session_active = True
        self._hosting_in_progress = False
        self.on_connection("connected")
        self._net_thread = threading.Thread(target=self._net_loop, daemon=True)
        self._net_thread.start()
        self._emit_board()

    def _net_loop(self):
        try:
            while self._running:
                # 1) Consome jogadas locais APENAS se jogo não acabou e é nossa vez
                if not self.game_over and self.turn == self.you:
                    try:
                        r, c = self._move_queue.get(timeout=0.1)
                        if self._apply_local_and_send(r, c):
                            self.turn = self.opponent
                            self._emit_board()
                            if self.game_over:
                                self._send_end_once()
                    except Empty:
                        pass

                # 2) Recebe mensagens remotas (inclui mensagens de revanche mesmo com jogo_over)
                try:
                    data = self._sock.recv(1024)
                except socket.timeout:
                    data = None
                except OSError:
                    self.on_message("Conexão perdida.")
                    self._session_active = False
                    break

                if not data:
                    continue

                msg = data.decode("utf-8").strip()
                if msg.startswith("END:"):
                    # Não derrubamos a conexão. Apenas refletimos o fim.
                    token = msg.split(":", 1)[1]
                    if token == "DRAW":
                        self._finish(None, show_message="Empate!")
                    else:
                        # token é "X" ou "O" (vencedor)
                        self._finish(token)
                    # loop continua para permitir rematch
                elif msg.upper() == "BYE":
                    self.on_message("Oponente saiu.")
                    self._session_active = False
                    break
                elif msg.startswith("REMATCH"):
                    self._handle_rematch_message(msg)
                else:
                    # Jogada remota, somente se jogo não acabou
                    if not self.game_over:
                        mv = self._parse_move(msg)
                        if mv and self._apply_remote(*mv):
                            self.turn = self.you
                            self._emit_board()
                            if self.game_over:
                                self._send_end_once()
                        else:
                            self.on_message(f"Jogada remota inválida: '{msg}'.")
                    # se jogo já acabou, ignoramos jogadas remotas

        finally:
            # Fecha apenas se ainda marcado como ativo (shutdown pode ter sido chamado)
            try:
                if self._sock:
                    self._sock.close()
            except Exception:
                pass
            self._sock = None
            self._session_active = False
            self.on_connection("disconnected")

    # ---------- Regras e protocolo ----------
    def _handle_rematch_message(self, msg: str):
        if msg == "REMATCH":
            # pedido sem troca de peças
            self.on_rematch("offer", {"swap": False})
            self.on_message("Oponente pediu revanche.")
        elif msg == "REMATCH:SWAP":
            self.on_rematch("offer", {"swap": True})
            self.on_message("Oponente pediu revanche (trocando X/O).")
        elif msg == "REMATCH:NO":
            self.on_rematch("declined", {})
            self.on_message("Oponente recusou a revanche.")
        elif msg == "REMATCH:OK" or msg == "REMATCH:OK:SWAP":
            swap = msg.endswith(":SWAP")
            self._start_rematch(swap=swap, initiator=True)
            self.on_rematch("accepted", {"swap": swap})

    def _start_rematch(self, swap: bool, initiator: bool):
        # Reseta tabuleiro e, opcionalmente, troca quem é X/O
        if swap:
            self.you, self.opponent = self.opponent, self.you
        self._reset_board()
        # por convenção, X sempre começa
        self.turn = "X"
        self.on_message("Revanche iniciada." + (" (Peças trocadas)" if swap else ""))
        self.on_rematch("start", {"you": self.you, "turn": self.turn})
        self._emit_board()

    def _parse_move(self, raw: str):
        try:
            parts = raw.split(",")
            if len(parts) != 2:
                return None
            r = int(parts[0].strip()); c = int(parts[1].strip())
            if 0 <= r < 3 and 0 <= c < 3:
                return (r, c)
        except Exception:
            return None
        return None

    def _cell_empty(self, r: int, c: int) -> bool:
        return self.board[r][c] == " "

    def _apply_local_and_send(self, r: int, c: int) -> bool:
        if not self._valid_turn(self.you):
            self.on_message("Ainda não é sua vez.")
            return False
        if not (0 <= r < 3 and 0 <= c < 3):
            self.on_message("Fora do tabuleiro.")
            return False
        if not self._cell_empty(r, c):
            self.on_message("Célula ocupada.")
            return False
        self._place_and_check(r, c, self.you)
        try:
            self._sock.send(f"{r},{c}".encode("utf-8"))
        except OSError:
            self.on_message("Falha ao enviar jogada. Conexão encerrada.")
            self._running = False
            self._session_active = False
        return True

    def _apply_remote(self, r: int, c: int) -> bool:
        if not self._valid_turn(self.opponent):
            return False
        if not (0 <= r < 3 and 0 <= c < 3):
            return False
        if not self._cell_empty(r, c):
            return False
        self._place_and_check(r, c, self.opponent)
        return True

    def _valid_turn(self, player: str) -> bool:
        return self.turn == player and not self.game_over

    def _place_and_check(self, r: int, c: int, player: str):
        with self._lock:
            if self.game_over:
                return
            self.board[r][c] = player
            self.counter += 1
            if self._check_is_won():
                self.game_over = True
                self.winner = player
                if player == self.you:
                    self.on_message("Você ganhou!!!")
                else:
                    self.on_message("Você perdeu!")
                self.on_over(self.winner)
            elif self.counter == 9:
                self.game_over = True
                self.winner = None
                self.on_message("Empate!")
                self.on_over(None)

    def _send_end_once(self):
        try:
            token = "DRAW" if self.winner is None else self.winner
            self._sock.send(f"END:{token}".encode("utf-8"))
        except Exception:
            pass

    def _emit_board(self):
        snap = [row[:] for row in self.board]
        self.on_board(snap, self.turn)

    def _check_is_won(self) -> bool:
        lines = (
            [(0,0),(0,1),(0,2)], [(1,0),(1,1),(1,2)], [(2,0),(2,1),(2,2)],
            [(0,0),(1,0),(2,0)], [(0,1),(1,1),(2,1)], [(0,2),(1,2),(2,2)],
            [(0,0),(1,1),(2,2)], [(0,2),(1,1),(2,0)]
        )
        for a,b,c in lines:
            v1 = self.board[a[0]][a[1]]
            v2 = self.board[b[0]][b[1]]
            v3 = self.board[c[0]][c[1]]
            if v1 == v2 == v3 != " ":
                return True
        return False

    def _finish(self, winner: Optional[str], show_message: Optional[str]=None):
        self.game_over = True
        self.winner = winner
        if show_message:
            self.on_message(show_message)
        elif winner is not None:
            self.on_message("Você ganhou!!!" if winner == self.you else "Você perdeu!")
        self.on_over(winner)
