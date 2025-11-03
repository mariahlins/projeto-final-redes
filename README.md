# Projeto Redes de Computadores: Jogo da Velha Multiplayer (Tick-Tack-Toe)

 Este projeto implementa o clássico jogo da velha com funcionalidade multiplayer via rede, utilizando comunicação TCP/IP com sockets e concorrência baseada em Threads[cite: 4, 5].

---

## Como rodar a aplicação?

A aplicação pode ser executada em dois modos: **Servidor (Host)** ou **Cliente (Conectar)**. Você precisará de dois terminais (ou dois computadores diferentes) para que o jogo funcione.

### Pré-requisitos

* **Python 3.x**
* Conexão de rede (o servidor e o cliente devem ser capazes de se comunicar).

### 1. Iniciar o Servidor (Host) - Jogador 'X'

O Host inicia o jogo e espera pela conexão do Cliente.

1.  **Abra o primeiro terminal.**
2.  **Execute o código Python** do projeto:

    ```bash
    python main.py
    ```

3.  O programa perguntará a você qual opção deseja. **Escolha a opção `1`** para Hostear o jogo.

    ```
    === Jogo da velha multiplayer ===
    1. Hostear o jogo (você será o X)
    2. Conectar com um jogo existente (você será o O)
    Escolha uma opção (1 ou 2): 1
    ```

4.  O servidor ficará em modo de espera:
    ```
    Esperando outro jogador se conectar em localhost:9999...
    ```

### 2. Conectar o Cliente - Jogador 'O'

O Cliente se conecta ao Servidor para iniciar o jogo.

1.  **Abra um segundo terminal.**
2.  **Execute o código Python** novamente:

    ```bash
    python main.py
    ```

3.  **Escolha a opção `2`** para Conectar com um jogo existente.

    ```
    === Jogo da velha multiplayer ===
    1. Hostear o jogo (você será o X)
    2. Conectar com um jogo existente (você será o O)
    Escolha uma opção (1 ou 2): 2
    ```

4.  A aplicação tentará se conectar ao endereço padrão (`localhost:9999`):
    ```
    Conectando a localhost:9999...
    Conectado ao jogo!
    ```

### 3. Jogando

* Assim que o cliente se conecta, o **Host ('X') sempre começa** a jogar.
* Quando for sua vez, o jogo solicitará a entrada no formato `linha,coluna`. As linhas e colunas são numeradas de `0` a `2`.

    **Exemplo de Jogada:** Para marcar a casa central, digite `1,1`.

    ```
    Digite sua entrada (linha, coluna): 1,1
    ```

* O jogo alterna entre os jogadores até que haja um vencedor (três em linha) ou um empate.

### 4. Fluxo de execução alternativo
* Se quiser executar a parte visual do jogo em uma interface gráfica, você pode utilizar a versão com Tkinter disponível no arquivo `ui_app.py`. O funcionamento é similar, mas com uma interface gráfica para facilitar a interação.
* Para rodar a versão gráfica, execute o seguinte comando em ambos os terminais:

    ```bash
    python ui_app.py
    ```

---

## 🛠️ Detalhes de Implementação (Requisitos do projeto atendidos)

*  **Linguagem:** Python.
*  **Comunicação:** Utiliza a biblioteca nativa `socket` para comunicação TCP/IP ponto a ponto e não Websocket como pedido.
*  **Concorrência:** O uso de **Threads** é obrigatório e está implementado na função `handle_connections` para que o jogo possa, simultaneamente, enviar (`send()`) e receber (`recv()`) dados em background, sem bloquear a interação do usuário.