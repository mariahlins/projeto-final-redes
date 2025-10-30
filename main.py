import socket
import threading

class TickTacToe():
    def __init__(self):
        self.board = [[" "," "," "],[" "," "," "],[" "," "," "]]
        self.turn = "X"
        self.you = "X"
        self.opponent = "O"
        self.winner = None
        self.game_over = False
        self.counter = 0

    def host_game(self, host, port):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((host, port))
        server.listen(1)
        
        print(f"Esperando outro jogador se conectar em {host}:{port}...")
        client, addr = server.accept()
        print(f"Oponente conectado de {addr}")
        
        self.you = "X"
        self.opponent = "O"
        threading.Thread(target=self.handle_connections, args=(client,)).start()
        server.close()

    def connect_to_game(self, host, port):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Conectando a {host}:{port}...")
        client.connect((host, port))
        print("Conectado ao jogo!")

        self.you = 'O'
        self.opponent = "X"
        threading.Thread(target=self.handle_connections, args=(client,)).start()

    def handle_connections(self, client):
        while not self.game_over:
            if self.turn == self.you:
                move = input("Digite sua entrada (linha, coluna): ")
                if self.check_valid_move(move.split(',')):
                    self.apply_move(move.split(','), self.you)
                    self.turn = self.opponent
                    client.send(move.encode('utf-8'))
                else:
                    print("Entrada inválida! Tente novamente.")
            
            else:
                data = client.recv(1024)
                if not data:
                    break
                else:
                    self.apply_move(data.decode('utf-8').split(','), self.opponent)
                    self.turn = self.you
        
        client.close()

    def apply_move(self, move, player):
        if self.game_over:
            return
        self.counter += 1
        self.board[int(move[0])][int(move[1])] = player
        self.print_board()
        if self.check_is_won():
            if self.winner == self.you:
                print("Você ganhou!!!")
                self.game_over = True
            elif self.winner == self.opponent:
                print("Você perdeu!")
                self.game_over = True
        else:
            if self.counter == 9:
                self.game_over = True
                print("It's a draw!")
        
    def check_valid_move(self, move):
        try:
            row, col = int(move[0]), int(move[1])
            return 0 <= row < 3 and 0 <= col < 3 and self.board[row][col] == " "
        except:
            return False

    def check_is_won(self):
        for row in range(3):
            if self.board[row][0] == self.board[row][1] == self.board[row][2] != " ":
                self.winner = self.board[row][0]
                self.game_over = True
                return True
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] != " ":
                self.winner = self.board[0][col]
                self.game_over = True
                return True
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != " ":
            self.winner = self.board[0][0]
            self.game_over = True
            return True
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != " ":
            self.winner = self.board[0][2]
            self.game_over = True
            return True
        return False

    def print_board(self):
        print("\n")
        for row in range(3):
            print(" | ".join(self.board[row]))
            if row < 2:
                print("-----------")
        print("\n")


if __name__ == "__main__":
    game = TickTacToe()
    
    print("=== Jogo da velha multiplayer ===")
    print("1. Hostear o jogo (você será o X)")
    print("2. Conectar com um jogo existente (você será o O)")
    
    choice = input("Escolha uma opção (1 ou 2): ")
    
    if choice == "1":
        game.host_game("localhost", 9999)
    elif choice == "2":
        game.connect_to_game("localhost", 9999)
    else:
        print("Opção inválida!")