import tkinter as tk
from tkinter import messagebox
from queue import Queue, Empty
from game_service import GameService

HOST = "localhost"
PORT = 9999

class TicTacToeUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Jogo da Velha (Multiplayer)")
        self.queue: Queue = Queue()
        self.svc = GameService(event_sink=self.queue.put)

        # grade de células
        self.cells = []
        grid = tk.Frame(root, padx=8, pady=8)
        grid.pack()
        for r in range(3):
            row = []
            for c in range(3):
                b = tk.Button(grid, text=" ", font=("Arial", 24), width=3, height=1,
                              command=lambda r=r, c=c: self.on_click(r, c))
                b.grid(row=r, column=c, padx=4, pady=4)
                row.append(b)
            self.cells.append(row)

        # status
        self.status = tk.Label(root, text="Selecione Host/Connect", anchor="w")
        self.status.pack(fill="x", padx=8, pady=4)

        # ações
        actions = tk.Frame(root)
        actions.pack(pady=4)
        self.btn_host = tk.Button(actions, text="Host (X)", command=self.host)
        self.btn_conn = tk.Button(actions, text="Connect (O)", command=self.connect)
        self.btn_quit = tk.Button(actions, text="Desconectar", command=self.disconnect, state="disabled")
        self.btn_rematch = tk.Button(actions, text="Revanche", command=self.rematch, state="disabled")
        self.btn_host.pack(side="left", padx=4)
        self.btn_conn.pack(side="left", padx=4)
        self.btn_rematch.pack(side="left", padx=4)
        self.btn_quit.pack(side="left", padx=4)

        # polling de eventos
        self.root.after(100, self.drain_events)

        # encerrar limpo
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # UI handlers
    def on_click(self, r, c):
        self.svc.make_move(r, c)

    def host(self):
        self.svc.host(HOST, PORT)
        self._set_connected_ui(pending=True)

    def connect(self):
        self.svc.connect(HOST, PORT)
        self._set_connected_ui(pending=True)

    def disconnect(self):
        self.svc.quit()
        self._set_disconnected_ui()

    def rematch(self):
        # pergunta se deseja trocar X/O
        swap = messagebox.askyesno("Revanche", "Deseja trocar as peças (X/O) na revanche?")
        self.svc.request_rematch(swap=swap)
        self.status.config(text="Pedido de revanche enviado...")

    # estado da UI
    def _set_connected_ui(self, pending=False):
        self.btn_host.config(state="disabled")
        self.btn_conn.config(state="disabled")
        self.btn_quit.config(state="normal")
        # rematch habilita apenas quando o jogo termina ou quando há uma oferta recebida
        self.btn_rematch.config(state="disabled")
        if pending:
            self.status.config(text="Conectando...")

    def _set_disconnected_ui(self):
        self.btn_host.config(state="normal")
        self.btn_conn.config(state="normal")
        self.btn_quit.config(state="disabled")
        self.btn_rematch.config(state="disabled")
        self.status.config(text="Desconectado.")

    # loop de eventos
    def drain_events(self):
        try:
            while True:
                evt = self.queue.get_nowait()
                self.handle_event(evt)
        except Empty:
            pass
        self.root.after(100, self.drain_events)

    def handle_event(self, evt: dict):
        etype = evt.get("type")
        if etype == "board_update":
            board = evt["board"]
            for r in range(3):
                for c in range(3):
                    self.cells[r][c]["text"] = board[r][c]
            # reabilita botões das células quando houver nova partida
            for r in range(3):
                for c in range(3):
                    self.cells[r][c]["state"] = "normal"
        elif etype == "message":
            self.status.config(text=evt["text"])
        elif etype == "game_over":
            winner = evt["winner"]
            msg = "Empate!" if winner is None else (f"Vencedor: {winner}")
            self.status.config(text=msg)
            # habilita botão de revanche
            self.btn_rematch.config(state="normal")
            # opcional: manter jogadas desabilitadas até rematch
            for r in range(3):
                for c in range(3):
                    self.cells[r][c]["state"] = "disabled"
        elif etype == "connection":
            state = evt["state"]
            if state == "connected":
                self._set_connected_ui(pending=False)
                self.status.config(text="Conectado.")
            elif state == "disconnected":
                self._set_disconnected_ui()
            elif state == "error":
                # volta botões para permitir tentar novamente
                self._set_disconnected_ui()
        elif etype == "rematch_offer":
            swap = evt.get("swap", False)
            txt = "Oponente pediu revanche" + (" (trocar X/O)?" if swap else "?")
            res = messagebox.askyesno("Revanche", txt + "\nAceitar?")
            self.svc.respond_rematch(accept=res, swap=swap)
            if res:
                self.status.config(text="Revanche aceita.")
            else:
                self.status.config(text="Revanche recusada.")
        elif etype == "rematch_accept":
            self.status.config(text="Oponente aceitou a revanche. Iniciando...")
        elif etype == "rematch_decline":
            self.status.config(text="Oponente recusou a revanche.")
            # continua desconectado, mas ainda conectados; jogador pode pedir de novo
        elif etype == "rematch_start":
            # nova partida começou
            self.btn_rematch.config(state="disabled")
            self.status.config(text="Nova partida iniciada.")

    def on_close(self):
        self.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    TicTacToeUI(root)
    root.mainloop()
